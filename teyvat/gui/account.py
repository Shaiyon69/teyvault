"""Account tab: HoYoLAB sign-in (browser window on PC, email + password with captcha on phones, or cookies)."""
import asyncio
import base64
import json
import threading

import flet as ft

from teyvat import db, hoyolab, vault, weblogin
from teyvat.gui import theme
from teyvat.gui.app import ACCOUNT, CHARACTERS, EVENTS, WISHES, WORLD
from teyvat.gui.theme import STRETCH
from teyvat.gui.widgets import card, hero, muted, skeleton

COOKIE_HELP = (
    "1. Log in at hoyolab.com in a desktop browser, and open genshin.hoyoverse.com/en/gift once.\n"
    "2. Press F12, then Application > Cookies.\n"
    "3. Copy ltoken_v2, ltuid_v2 (hoyolab.com) and cookie_token_v2, account_id_v2 (hoyoverse.com).\n"
    "4. Paste them below as: ltoken_v2=...; ltuid_v2=...; cookie_token_v2=...; account_id_v2=..."
)
# HoYoLAB's Geetest v3 captcha for the phone login, in a WebView. The solved result comes back as a
# console message and in document.title, which Python polls in case the console channel stays silent.
CAPTCHA_HTML = """<!doctype html><html><head><meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://static.geetest.com/static/js/gt.0.5.0.js"></script></head>
<body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;font:15px sans-serif;
color:#888"><div id="msg">Loading captcha...</div><script>
initGeetest({gt: "__GT__", challenge: "__CHALLENGE__", new_captcha: true, api_server: "api-na.geetest.com", https: true,
             product: "bind", lang: "en"}, function (c) {
  c.onReady(function () { document.getElementById("msg").textContent = "Solve the captcha"; c.verify(); });
  c.onClose(function () { document.getElementById("msg").textContent = "Tap to try again"; document.body.onclick = function () { c.verify(); }; });
  c.onError(function () { document.getElementById("msg").textContent = "The captcha failed to load."; });
  c.onSuccess(function () {
    var v = JSON.stringify(c.getValidate());
    document.getElementById("msg").textContent = "Verifying...";
    console.log("geetest:" + v);
    document.title = "geetest:" + v;
  });
});
</script></body></html>"""


def build(app):
    page, toast, guarded, logged_in = app.page, app.toast, app.guarded, app.logged_in
    ensure_loaded, page_head, has_webview = app.ensure_loaded, app.page_head, app.has_webview
    active_role, bound_roles, loaded, current = app.active_role, app.bound_roles, app.loaded, app.current
    GOLD, _, WON, LOST = theme.accents()

    account_icon = ft.Icon(ft.Icons.NO_ACCOUNTS_ROUNDED, size=28)
    account_title = ft.Text(size=18, weight=ft.FontWeight.W_600)
    account_sub = muted("")
    logout_btn = ft.OutlinedButton("Sign out", icon=ft.Icons.LOGOUT_ROUNDED)
    status_dot = ft.Container(width=8, height=8, border_radius=4)
    status_label = ft.Text(size=13, weight=ft.FontWeight.W_500)
    cookie_field = ft.TextField(label="HoYoLAB cookies", password=True, can_reveal_password=True,
                                border_radius=14, filled=True)
    profiles = ft.Column(spacing=16, horizontal_alignment=STRETCH)

    def role_card(r):
        count = db.count_wishes(db.connect(), r["game_uid"])
        return hero(ft.Row([
            ft.Container(ft.Text(r["nickname"][:1].upper(), size=24, weight=ft.FontWeight.BOLD,
                                 color="#1B1608"),
                         width=56, height=56, border_radius=28, alignment=ft.Alignment.CENTER,
                         gradient=ft.LinearGradient(colors=[GOLD, "#C9965A"])),
            ft.Column([
                ft.Text(r["nickname"], size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                muted(f"{r['region_name']} · UID {r['game_uid']}"),
                muted(f"{count:,} wishes logged" if count else "No wishes logged yet", size=13),
            ], spacing=2, expand=True),
            ft.Column([ft.Text(str(r["level"]), size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                       muted("AR", size=12)], spacing=0,
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=16))

    def load_profiles():
        """Fetch the Genshin accounts bound to this HoYoLAB login (runs on a worker thread)."""
        roles = []
        if not logged_in():
            profiles.controls = []
        else:
            profiles.controls = [skeleton(1, height=104)]
            profiles.update()
            try:
                roles = hoyolab.game_roles(vault.load())
                bound_roles[:] = roles
                profiles.controls = [role_card(r) for r in roles] or [
                    card(muted("No Genshin account bound to this HoYoLAB login."))]
            except Exception as ex:
                profiles.controls = [card(muted(f"Could not load game accounts: {ex}"))]
        app.account_pick.options = [ft.DropdownOption(r["game_uid"], f"{r['nickname']} · UID {r['game_uid']}")
                                for r in roles]
        app.account_pick.value = active_role()["game_uid"] if roles else None
        app.account_row.visible = len(roles) > 1  # a picker with one choice is just noise
        page.update()
        ensure_loaded(current["i"])
        app.load_resin()

    def signed_in(cookies):
        vault.save(cookies)
        cookie_field.value = ""
        show_auth()
        page.update()
        page.run_thread(app.load_rewards)
        page.run_thread(load_profiles)
        if "cookie_token_v2" not in cookies:
            return "Signed in. No cookie_token_v2, so redeeming codes will not work."
        return "Signed in."

    def do_signin():
        toast("Log in on the HoYoLAB window. It closes by itself when you are done.")
        return signed_in(weblogin.sign_in())

    def solve_captcha(need):
        """Show HoYoLAB's captcha in a WebView and block until it is solved (worker thread)."""
        import flet_webview  # NOTE: its console channel is Android/iOS/macOS only; Windows uses weblogin instead
        solved, done = {}, threading.Event()

        def got(result):
            if not done.is_set():
                solved.update(json.loads(result))
                done.set()

        def on_message(e):
            if e.message.startswith("geetest:"):
                got(e.message.removeprefix("geetest:"))

        html = CAPTCHA_HTML.replace("__GT__", need.gt).replace("__CHALLENGE__", need.challenge)
        view = flet_webview.WebView(url="data:text/html;base64," + base64.b64encode(html.encode()).decode(),
                                    on_console_message=on_message, expand=True)
        page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Confirm it's you"), inset_padding=ft.Padding.all(12),
            content=ft.Container(view, width=(page.width or 360) - 72, height=420),
            actions=[ft.TextButton("Cancel", on_click=lambda e: done.set())]))
        for _ in range(600):  # 5 minutes
            if done.wait(0.5):
                break
            try:
                title = asyncio.run_coroutine_threadsafe(view.get_title(), page.loop).result(5) or ""
            except Exception:  # not mounted yet, or the platform can't report it
                continue
            if title.startswith("geetest:"):
                got(title.removeprefix("geetest:"))
        page.pop_dialog()
        if not solved:
            raise RuntimeError("Sign-in cancelled." if done.is_set() else "The captcha timed out. Try again.")
        return solved

    def do_password_login():
        account, password = (login_account.value or "").strip(), login_password.value or ""
        if not account or not password:
            return "Enter your HoYoLAB email and password."
        captcha = None
        for attempt in range(3):  # HoYoLAB sometimes asks for a fresh captcha after a solved one
            try:
                cookies = hoyolab.login(account, password, captcha)
                break
            except hoyolab.CaptchaRequired as need:
                if attempt == 2:
                    return "HoYoLAB kept rejecting the captcha. Try again later, or use browser cookies."
                captcha = (need, solve_captcha(need))
        cookies = {k: v for k, v in cookies.items() if k in vault.WANTED}
        if "ltoken_v2" not in cookies:
            return "HoYoLAB did not return a login. Try again, or use browser cookies."
        login_password.value = ""
        return signed_in(cookies)

    def do_cookie_login():
        cookies = vault.parse_cookie_string(cookie_field.value or "")
        missing = [k for k in ("ltoken_v2", "ltuid_v2") if k not in cookies]
        if missing:
            return f"Missing {', '.join(missing)}."
        return signed_in(cookies)

    def do_logout(e):
        page.pop_dialog()
        vault.delete()
        bound_roles.clear()
        loaded.difference_update({EVENTS, WISHES, WORLD, CHARACTERS})
        app.account_row.visible = False
        profiles.controls = []
        app.reset_world()
        app.reset_chars()
        show_auth()
        page.update()
        toast("Signed out.")

    def confirm_logout(e):
        # Signing back in means fetching cookies again, so ask before throwing them away.
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Sign out of HoYoLAB?"),
            content=muted("Your wish history stays on this device. You'll need to sign in again to "
                          "check in, redeem codes and see exploration."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                     ft.FilledButton("Sign out", on_click=do_logout)]))

    logout_btn.on_click = confirm_logout

    # PC: the real hoyolab.com page in a window. Phones (no such window): email + password, sent only to
    # HoYoLAB like its login page does; a captcha, if HoYoLAB asks, opens in a WebView.
    login_account = ft.TextField(label="Email or username", border_radius=14, filled=True,
                                 keyboard_type=ft.KeyboardType.EMAIL, prefix_icon=ft.Icons.ALTERNATE_EMAIL_ROUNDED)
    login_password = ft.TextField(label="Password", password=True, can_reveal_password=True, border_radius=14,
                                  filled=True, prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
                                  on_submit=guarded(do_password_login))
    signin_card = card(
        muted("Opens the official hoyolab.com login. Teyvault never sees your password."),
        ft.Row([ft.FilledButton("Sign in with HoYoLAB", icon=ft.Icons.LOGIN_ROUNDED, on_click=guarded(do_signin))]),
        title="Sign in with HoYoLAB") if has_webview else card(
        muted("Your HoYoLAB email and password go straight to HoYoLAB, encrypted. Teyvault never stores "
              "your password."),
        login_account, login_password,
        ft.FilledButton("Sign in with HoYoLAB", icon=ft.Icons.LOGIN_ROUNDED, on_click=guarded(do_password_login)),
        title="Sign in with HoYoLAB")
    cookie_card = card(ft.ExpansionTile(
        title=ft.Text("Use browser cookies instead"), tile_padding=0,
        controls_padding=ft.Padding.only(bottom=8), shape=ft.RoundedRectangleBorder(),
        collapsed_shape=ft.RoundedRectangleBorder(),
        expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
        controls=[ft.Column([
            muted(COOKIE_HELP),
            ft.Text("These cookies give full access to your HoYoLAB account. Never share them.",
                    color=ft.Colors.ERROR, size=13),
            cookie_field,
            ft.FilledTonalButton("Save cookies", icon=ft.Icons.SAVE_ROUNDED,
                                 on_click=guarded(do_cookie_login)),
        ], spacing=12)],
    ))

    def show_auth():
        """Show only what makes sense for the current login state, on every tab."""
        on = logged_in()
        account_icon.icon = ft.Icons.VERIFIED_USER_ROUNDED if on else ft.Icons.NO_ACCOUNTS_ROUNDED
        account_icon.color = WON if on else ft.Colors.ON_SURFACE_VARIANT
        account_title.value = "Signed in to HoYoLAB" if on else "Not signed in"
        account_sub.value = ("Credentials stay on this device." if on
                             else "Sign in to check in, redeem codes and see exploration.")
        logout_btn.visible = on
        signin_card.visible = not on
        cookie_card.visible = not on
        status_dot.bgcolor = WON if on else LOST
        status_label.value = "Signed in" if on else "Signed out"
        app.show_dashboard_auth(on)

    app.show_auth, app.load_profiles = show_auth, load_profiles
    app.status_dot, app.status_label = status_dot, status_label
    return ft.Column([
        page_head(ACCOUNT),
        card(ft.Row([account_icon, ft.Column([account_title, account_sub], spacing=2, expand=True),
                     logout_btn], spacing=16)),
        profiles,
        signin_card,
        cookie_card,
    ], spacing=16, horizontal_alignment=STRETCH)
