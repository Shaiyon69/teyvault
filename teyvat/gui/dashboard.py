"""Dashboard tab: account stats, today's domains, daily check-in rewards and promo codes."""
import datetime

import flet as ft

from teyvat import db, hoyolab, vault, wiki
from teyvat.gui import theme
from teyvat.gui.theme import STRETCH
from teyvat.gui.widgets import bar, card, item_icon, label, muted, reward_tile, skeleton, today

PRIMOGEM_ICON = "https://cdn.jsdelivr.net/gh/MadeBaruna/paimon-moe@main/static/images/primogem.png"


def build(app):
    page, phone = app.page, app.phone
    active_role, guarded, logged_in = app.active_role, app.guarded, app.logged_in
    page_head, signin_prompt = app.page_head, app.signin_prompt
    GOLD, _, WON, LOST = theme.accents()

    # PC/tablet: one screen, never scrolls. Head card, a row of live stats, then today's domains and
    # the code box on the left beside the reward calendar; only the domains and calendar scroll, inside their cards.
    # Phones: the same cards stacked in the page's scroll.
    codes = ft.TextField(hint_text="Redeem a promo code",
                         border_radius=14, filled=True, dense=True, expand=True)
    redeem_results = ft.Column(spacing=4)
    dash_sub = muted("", size=14 if phone else 16)  # greeting with the active account, set by load_resin

    checkin_btn = ft.FilledButton("Check in", icon=ft.Icons.TOUCH_APP_ROUNDED)

    def show_auto_note():
        checkin_btn.tooltip = ("Teyvault checks in for you once a day when the app opens." if app.auto_on()
                               else "Automatic check-in is off (Settings).")

    def show_checkin(last):
        checkin_btn.visible = last != today()  # nothing to press once it's done; the calendar shows the tick

    def do_checkin():
        result = hoyolab.checkin(vault.load())
        db.set_meta(db.connect(), "last_checkin", today())
        show_checkin(today())
        page.update()
        return result

    # columns = tiles per row, so the calendar fills the card instead of leaving a gap on the right
    rewards_grid = ft.ResponsiveRow(columns=5 if phone else 7, spacing=6, run_spacing=6)
    rewards_sub = muted("", size=12)
    rewards_status = muted("", size=12)  # "5/31 claimed · checked in today"
    # PC: the card fills its column; a short window scrolls the calendar inside it, not the page
    rewards_card = card(ft.Row([label("Daily rewards", expand=True), rewards_status, checkin_btn], spacing=12,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        rewards_sub, ft.Column([rewards_grid], scroll=None if phone else ft.ScrollMode.AUTO,
                                               expand=not phone),
                        visible=False, expand=not phone)

    month = {}  # the last checkin_month answer, redrawn on resize

    def show_rewards():
        """Reward tiles sized so the calendar fills its card (PC); phones keep fixed tiles in the page scroll."""
        m = month.get("m")
        if not m:
            return
        signed, done = m["signed"], m["today_done"]
        current = signed - 1 if done else signed
        icon, height = 40, None
        if not phone:
            w, h = app.content_size()
            cols = rewards_grid.columns
            rows = -(-len(m["awards"]) // cols)
            height = max(84, int((h - 170) / rows) - 6)  # minus head card, card padding and its header row
            width = ((w - 16) / 2 - 42) / cols - 6
            icon = int(max(32, min(72, height - 48, width - 16)))
        rewards_grid.controls = [reward_tile(i + 1, a, i < signed, i == current and not m["error"], icon, height)
                                 for i, a in enumerate(m["awards"])]

    def load_rewards():
        """Fill the reward calendar from HoYoLAB (runs on a worker thread)."""
        rewards_card.visible = logged_in()
        if rewards_card.visible:
            rewards_sub.value, rewards_status.value = "", ""
            rewards_grid.controls = [ft.Container(skeleton(14, tile=70), col=rewards_grid.columns)]
            page.update()
            try:
                m = hoyolab.checkin_month(vault.load())
                wiki.cache_images(a["icon"] for a in m["awards"])
            except Exception as ex:
                rewards_sub.value, rewards_grid.controls = f"Could not load rewards: {ex}", []
            else:
                signed, done = m["signed"], m["today_done"]
                month["m"] = m
                show_rewards()
                rewards_sub.value = f"Could not load your progress: {m['error']}" if m["error"] else ""
                if not m["error"]:
                    rewards_status.value = (f"{signed}/{len(m['awards'])} claimed"
                                            + (" · checked in today" if done else ""))
                if done:  # trust the server, e.g. checked in from another device
                    db.set_meta(db.connect(), "last_checkin", today())
                    show_checkin(today())
        rewards_sub.visible = bool(rewards_sub.value)  # only errors; an empty line would leave a gap
        page.update()

    def do_checkin_and_refresh():
        result = do_checkin()
        load_rewards()
        return result

    def do_redeem():
        todo = [c for c in codes.value.split() if c]
        if not todo:
            return "Enter at least one code."
        redeem_results.controls = [muted(f"Redeeming {len(todo)} code(s), ~6s each...", size=12)]
        redeem_results.update()
        results = hoyolab.redeem(vault.load(), todo)
        redeem_results.controls = [
            ft.Row([ft.Text(c, size=13, weight=ft.FontWeight.W_600, font_family="monospace"), muted(r, size=12)],
                   wrap=True) for c, r in results]
        redeem_results.update()

    checkin_btn.on_click = guarded(do_checkin_and_refresh)

    # Stats: resin, commissions, realm currency and expeditions, one card each, 2 per row
    # (PC: above the domains in the left column, so the rewards calendar gets the full height).
    resin_strip = resin_card = ft.ResponsiveRow(spacing=16, run_spacing=16, visible=False)
    stat_col = 6

    def load_resin():
        """Worker thread, after the game accounts are known. Real-time notes of the active account."""
        role = active_role()
        resin_card.visible = role is not None
        dash_sub.value = (f"{role['nickname']} · AR {role['level']} · {role['region_name']}" if role
                          else "Sign in to HoYoLAB to see your account here.")
        load_primos()  # the ledger is per game account
        if not role:
            page.update()
            return
        resin_strip.controls = [ft.Container(skeleton(1, height=52), col=12)]
        page.update()
        try:
            n = hoyolab.daily_note(vault.load(), role)
        except Exception as ex:
            resin_strip.controls = [card(muted(f"Could not load resin: {ex}. Turn on Real-time Notes in "
                                               "HoYoLAB's Battle Chronicle settings.", size=13), col=12)]
        else:
            cur, cap, left = n["current_resin"], n["max_resin"], int(n["resin_recovery_time"])
            full = (datetime.datetime.now() + datetime.timedelta(seconds=left)).strftime("%a %H:%M")
            color = LOST if cur >= cap else ft.Colors.PRIMARY
            # compact cards: label and value on one line, a small note (or the resin bar) under it
            def stat(name, text, note, color=None):
                return card(ft.Column([
                    ft.Row([label(name, expand=True), ft.Text(text, size=15, weight=ft.FontWeight.W_600,
                                                              color=color)], spacing=6),
                    note if isinstance(note, ft.Control) else muted(note, size=11),
                ], spacing=4, horizontal_alignment=STRETCH), col=stat_col,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10))

            resin_strip.controls = [
                stat("Original Resin", f"{cur}/{cap}",
                     ft.Row([bar(cur / cap, color, height=4), muted("Full" if left <= 0 else f"full {full}", size=11)],
                            spacing=6), color),
                stat("Commissions", f"{n['finished_task_num']}/{n['total_task_num']}", "done today"),
                stat("Realm currency", f"{n['current_home_coin']:,}", f"of {n['max_home_coin']:,}"),
                stat("Expeditions", f"{n['current_expedition_num']}/{n['max_expedition_num']}", "dispatched"),
            ]
        page.update()

    # Primogems: no API returns the balance, so the player types it in (e.g. before closing the game);
    # the saved counts are their ledger, each with the change since the one before.
    primo_text = ft.Text(color=GOLD, weight=ft.FontWeight.W_600)
    primo_btn = ft.TextButton(ft.Row([ft.Image(src=wiki.image(PRIMOGEM_ICON), width=20, height=20), primo_text],
                                     spacing=6, tight=True), tooltip="Primogems: tap to update")
    primo_field = ft.TextField(hint_text="Current primogems", keyboard_type=ft.KeyboardType.NUMBER,
                               border_radius=14, filled=True, dense=True, expand=True)
    primo_log = ft.Column(spacing=2)

    def primo_uid():
        role = active_role()
        return role["game_uid"] if role else ""

    def load_primos():
        rows = db.primogem_log(db.connect(), primo_uid())
        primo_text.value = f"{rows[0]['count']:,}" if rows else "Primogems"
        primo_log.controls = []
        for r, prev in zip(rows, rows[1:] + [None]):
            diff = r["count"] - prev["count"] if prev else 0
            when = datetime.datetime.fromisoformat(r["time"]).strftime("%a %d %b %H:%M")
            primo_log.controls.append(ft.Row([
                muted(when, size=12, expand=True), muted(f"{r['count']:,}", size=12),
                ft.Text(f"{diff:+,}" if prev else "", size=12, width=64, text_align=ft.TextAlign.RIGHT,
                        color=WON if diff > 0 else LOST if diff < 0 else ft.Colors.ON_SURFACE_VARIANT)]))

    def save_primos():
        text = (primo_field.value or "").replace(",", "").strip()
        if not text.isdigit():
            return "Enter your primogem count as a number."
        db.log_primogems(db.connect(), primo_uid(), int(text))
        primo_field.value = ""
        load_primos()
        page.update()

    primo_btn.on_click = lambda e: page.show_dialog(ft.AlertDialog(
        title=ft.Text("Primogems"), actions=[ft.TextButton("Close", on_click=lambda ev: page.pop_dialog())],
        content=ft.Container(ft.Column([
            ft.Row([primo_field, ft.FilledTonalButton("Save", icon=ft.Icons.SAVE_ROUNDED,
                                                      on_click=guarded(save_primos))],
                   spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            primo_log], spacing=12, tight=True), width=380)))
    load_primos()
    # account line with the primogem count right after it, in the head card
    dash_sub.max_lines, dash_sub.overflow = 1, ft.TextOverflow.ELLIPSIS
    dash_line = ft.Row([ft.Container(dash_sub, expand=True, expand_loose=True), primo_btn], spacing=4,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # PC: the card fills the rest of its column and icons wrap downwards; a short window scrolls inside it
    domains_body = ft.Column([skeleton(2, height=24)], spacing=6, horizontal_alignment=STRETCH,
                             scroll=None if phone else ft.ScrollMode.AUTO, expand=not phone)
    domains_sub = muted("", size=12)

    def pick_domains(e):
        """Show only the chosen group (characters or weapons) so the card doesn't need scrolling."""
        for c in domains_body.controls:
            c.visible = c.data in (None, e.control.selected[0])
        domains_body.update()

    domains_pick = ft.SegmentedButton(selected=["talent"], show_selected_icon=False, on_change=pick_domains,
                                      segments=[ft.Segment("talent", label="Characters",
                                                           icon=ft.Icons.PERSON_ROUNDED),
                                                ft.Segment("weapon", label="Weapons",
                                                           icon=ft.Icons.SHIELD_ROUNDED)])
    domains_card = card(domains_sub, domains_pick, domains_body, title="Today's domains", expand=not phone,
                        padding=21 if phone else ft.Padding.symmetric(horizontal=21, vertical=16))

    def load_domains():
        """Worker thread. Talent books and weapon materials farmable today, by the active account's server."""
        role = active_role()
        try:
            mats = wiki.todays_domains(wiki.farming(db.connect()), role and role["region"])
        except Exception as ex:
            domains_body.controls = [muted(f"Could not load today's domains: {ex}", size=13)]
        else:
            day = wiki.farm_day(role and role["region"])
            domains_sub.value = ("Sunday: every domain is open." if day == 6 else
                                 f"{wiki.DAYS[day].title()}, until 04:00 server time. Sunday opens them all.")
            farm["mats"] = mats
            show_domains()
        page.update()

    farm = {}  # today's materials, redrawn on resize

    def domain_icon_size(n):
        """Largest icon (32-72 px) at which n icons fit the card without scrolling (PC)."""
        if phone:
            return 38
        w, h = app.content_size()
        w = (w - 16) / 2 - 42 + 4  # the left column, minus card padding; +4 for the last icon's missing gap
        h -= 99 + 134 + (158 if resin_card.visible else 0)  # head card, the card's own chrome, the stat cards
        return next((s for s in range(72, 32, -2) if -(-n // max(1, int(w // (s + 4)))) * (s + 4) <= h), 32)

    def show_domains():
        # just who can farm today, no material names: one wrapping block of icons per kind, one kind shown
        mats = farm.get("mats")
        if mats is None:
            return
        groups = [(key, kind, [(n, r) for m in mats if m["kind"] == key for n, r in m["items"]])
                  for key, kind in (("talent", "Character"), ("weapon", "Weapon"))]
        size = domain_icon_size(max(len(items) for *_, items in groups))
        domains_body.controls = [ft.Row([item_icon(n, kind, size, r) for n, r in items],
                                        wrap=True, spacing=4, run_spacing=4, data=key,
                                        visible=key == domains_pick.selected[0])
                                 for key, kind, items in groups]

    redeem_card = card(ft.Row([codes, ft.FilledTonalButton("Redeem", icon=ft.Icons.REDEEM_ROUNDED,
                                                           on_click=guarded(do_redeem))],
                              spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                       redeem_results, padding=ft.Padding.symmetric(horizontal=16, vertical=16),
                       width=None if phone else 420)
    today_locked = signin_prompt("Sign in to HoYoLAB to check in, see your rewards and redeem codes.")

    if phone:
        today_view = ft.Column([page_head(0, sub=dash_line, inline=True), resin_card, today_locked, rewards_card, domains_card,
                                redeem_card], spacing=16, horizontal_alignment=STRETCH)
    else:
        today_view = ft.Column([
            page_head(0, redeem_card, sub=dash_line, inline=True),
            ft.Row([
                ft.Column([resin_card, today_locked, domains_card], spacing=16, horizontal_alignment=STRETCH,
                          expand=True),
                ft.Column([rewards_card], spacing=16, horizontal_alignment=STRETCH, expand=True),
            ], spacing=16, expand=True, vertical_alignment=STRETCH),
        ], spacing=16, horizontal_alignment=STRETCH, expand=True)


    def show_auth(on):
        redeem_card.visible = on
        today_locked.visible = not on
        if not on:
            rewards_card.visible = resin_card.visible = False

    def fit():
        show_rewards()
        show_domains()

    if not phone:
        app.on_resize.append(fit)
    app.load_rewards, app.load_resin, app.load_domains = load_rewards, load_resin, load_domains
    app.do_checkin, app.show_checkin, app.show_auto_note = do_checkin, show_checkin, show_auto_note
    app.show_dashboard_auth = show_auth
    return today_view
