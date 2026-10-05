"""Settings tab: preferences, phone sync over the LAN, import/export/delete of wish data, About."""
import json

import flet as ft

from teyvat import __version__, db, lansync, wish
from teyvat.gui import theme
from teyvat.gui.app import CHARACTERS, EVENTS, SETTINGS, WISHES, WORLD
from teyvat.gui.theme import APP, APP_AUTHOR, APP_REPO, SEEDS, STRETCH, STYLES, THEMES
from teyvat.gui.widgets import card, logo_badge, muted


def build(app):
    page, phone, mobile, toast, guarded = app.page, app.phone, app.mobile, app.toast, app.guarded
    page_head, ensure_loaded, loaded, current = app.page_head, app.ensure_loaded, app.loaded, app.current
    mode, style, seed = app.prefs  # theme mode, style, Material You seed
    GOLD = theme.accents()[0]

    def set_auto_checkin(e):
        db.set_meta(db.connect(), "auto_checkin", "1" if e.control.value else "0")
        app.show_auto_note()
        page.update()

    def set_pref(key):
        def handler(e):
            db.set_meta(db.connect(), key, e.control.value)
            if share["server"]:  # the rebuilt tab would lose the handle to stop it
                share["server"].close()
            app.restart()
        return handler

    style_pick = ft.Dropdown(label="Style", value=style, width=220, dense=True, filled=True, border_radius=14,
                             options=[ft.DropdownOption(k, v) for k, v in STYLES.items()], on_select=set_pref("style"))
    seed_pick = ft.Dropdown(label="Material You color", value=seed, width=220, dense=True, filled=True,
                            border_radius=14, visible=style == "material", on_select=set_pref("seed"),
                            options=[ft.DropdownOption(k, v, leading_icon=ft.Icon(ft.Icons.CIRCLE_ROUNDED, color=k))
                                     for k, v in SEEDS.items()])

    def set_account(e):
        db.set_meta(db.connect(), "default_uid", e.control.value)
        app.uid_pick.value = None  # let the Wishes tab follow the new default
        app.refresh_stats()
        loaded.difference_update({EVENTS, WISHES, WORLD, CHARACTERS})
        ensure_loaded(current["i"])
        page.run_thread(app.load_resin)

    account_pick = ft.Dropdown(label="Game account", width=min(320, (page.width or 360) - 72) if phone else 320, dense=True, filled=True, border_radius=14,
                               on_select=set_account)
    account_row = ft.Column([muted("Which account World, Characters and Wishes show first."), account_pick],
                            spacing=8, visible=False)
    prefs_card = card(
        ft.Switch(label="Check in automatically when Teyvault opens", value=app.auto_on(), on_change=set_auto_checkin),
        ft.Row([ft.Dropdown(label="Mode", value=mode, width=220, dense=True, filled=True, border_radius=14,
                            options=[ft.DropdownOption(k, v) for k, v in THEMES.items()], on_select=set_pref("theme")),
                style_pick, seed_pick], wrap=True, spacing=12, run_spacing=12),
        muted("Clean: flat grey layers. Classic: the original purple look. Material You: Google's tonal colors. Glass: frosted, translucent "
              "cards. Nothing: black, white and one red.", size=12),
        account_row,
        title="Preferences")

    # Phone sync: the PC serves its wish history on the Wi-Fi, the phone pulls it with a one-time PIN.
    share = {"server": None}
    share_addr = ft.Text(size=22, weight=ft.FontWeight.BOLD, selectable=True, font_family="monospace")
    share_pin = ft.Text(size=22, weight=ft.FontWeight.BOLD, selectable=True, font_family="monospace", color=GOLD)
    share_info = ft.Row([ft.Column([muted("Address", size=12), share_addr], spacing=0),
                         ft.Column([muted("PIN", size=12), share_pin], spacing=0)],
                        spacing=32, wrap=True, visible=False)
    share_btn = ft.FilledTonalButton("Start sharing", icon=ft.Icons.PHONELINK_RING_ROUNDED)

    def toggle_share():
        if share["server"]:
            share["server"].close()
            share["server"] = None
        else:
            ip = lansync.local_ip()
            payload = json.dumps(wish.export_uigf(db.connect()), ensure_ascii=False).encode()
            share["server"] = lansync.Share(payload)
            share_addr.value, share_pin.value = f"{ip}:{share['server'].port}", share["server"].pin
        on = share["server"] is not None
        share_info.visible = on
        share_btn.content = "Stop sharing" if on else "Start sharing"
        share_btn.icon = ft.Icons.STOP_CIRCLE_OUTLINED if on else ft.Icons.PHONELINK_RING_ROUNDED
        page.update()

    share_btn.on_click = guarded(toggle_share)
    pc_addr = ft.TextField(label="PC address", hint_text="192.168.1.20:47320", border_radius=14, filled=True,
                           value=db.get_meta(db.connect(), "pc_address", ""), keyboard_type=ft.KeyboardType.URL)
    pc_pin = ft.TextField(label="PIN", border_radius=14, filled=True, max_length=6, width=160,
                          keyboard_type=ft.KeyboardType.NUMBER)

    def do_receive():
        data = lansync.pull(pc_addr.value or "", pc_pin.value or "")
        conn = db.connect()
        added = wish.import_uigf(conn, data)
        db.drop_covered_synthetic(conn)
        db.set_meta(conn, "pc_address", pc_addr.value.strip())
        pc_pin.value = ""
        app.refresh_stats()
        return f"Received {added} new wishes."

    phone_card = card(
        muted("On Teyvault for PC, open Settings > Phone sync and press Start sharing, then enter the address "
              "and PIN it shows. Both devices must be on the same Wi-Fi. Only wish history is sent, never "
              "your sign-in."),
        pc_addr, ft.Row([pc_pin, ft.FilledButton("Receive", icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=guarded(do_receive))],
                        spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
        title="Receive from PC") if mobile else card(
        muted("Send your wish history to Teyvault on your phone. Both devices must be on the same Wi-Fi. "
              "On the phone, open Settings > Receive from PC and enter the address and PIN below. Only "
              "wish history is sent, never your sign-in. Sharing stops after 5 wrong PINs."),
        share_info, ft.Row([share_btn]),
        title="Phone sync")

    del_count = ft.Text(weight=ft.FontWeight.W_600, color=ft.Colors.ERROR)
    del_ok = ft.Checkbox(label="I understand this cannot be undone")
    danger = ft.ButtonStyle(bgcolor=ft.Colors.ERROR, color=ft.Colors.ON_ERROR)
    del_btn = ft.FilledButton("Delete", icon=ft.Icons.DELETE_FOREVER_ROUNDED, disabled=True)

    def show_del_count(e=None):
        n = db.count_wishes(db.connect(), del_pick.value)
        del_count.value = f"{n:,} wishes of UID {del_pick.value} will be deleted."
        if e:
            del_count.update()

    def arm_delete(e):
        del_btn.disabled = not del_ok.value
        del_btn.style = None if del_btn.disabled else danger  # red only once armed
        del_btn.update()

    del_ok.on_change = arm_delete
    del_pick = ft.Dropdown(label="Account", width=220, dense=True, filled=True, border_radius=14,
                           on_select=show_del_count)

    def do_delete(e):
        page.pop_dialog()
        removed = db.delete_wishes(db.connect(), del_pick.value)
        app.refresh_stats()
        toast(f"Deleted {removed:,} wishes for UID {del_pick.value}.")

    del_btn.on_click = do_delete

    def confirm_delete(e):
        uids = db.uids(db.connect())
        if not uids:
            toast("No wish history stored.")
            return
        del_pick.options = [ft.DropdownOption(u, f"UID {u}") for u in uids]
        del_pick.value = uids[-1]
        del_ok.value, del_btn.disabled, del_btn.style = False, True, None
        show_del_count()
        page.show_dialog(ft.AlertDialog(
            icon=ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.ERROR, size=36),
            title=ft.Text("Delete wish history?"),
            content=ft.Column([
                muted("This permanently removes every stored wish of the account from this device. The game "
                      "only keeps the last 6 months of history, so older pulls can never be synced back."),
                del_pick, del_count,
                ft.OutlinedButton("Export a backup first", icon=ft.Icons.SAVE_ALT_ROUNDED, on_click=app.do_export),
                del_ok,
            ], tight=True, spacing=12),
            actions=[ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()), del_btn]))

    data_card = card(
        muted("Wish history is stored in:"),
        ft.Text(str(db.default_path()), selectable=True, size=13, font_family="monospace"),
        ft.Row([ft.FilledTonalButton("Import file", icon=ft.Icons.FILE_OPEN_ROUNDED, on_click=app.do_import,
                                     tooltip="UIGF JSON or Excel from another wish tracker"),
                ft.OutlinedButton("Export UIGF", icon=ft.Icons.SAVE_ALT_ROUNDED, on_click=app.do_export),
                ft.OutlinedButton("Export Excel", icon=ft.Icons.TABLE_VIEW_ROUNDED, on_click=app.do_export_xlsx)],
               wrap=True, spacing=8, run_spacing=8),
        ft.Row([ft.OutlinedButton("Delete wish history", icon=ft.Icons.DELETE_OUTLINE_ROUNDED, on_click=confirm_delete,
                                  style=ft.ButtonStyle(color=ft.Colors.ERROR))]),
        title="Your data")

    about_card = card(
        ft.Row([logo_badge(), ft.Column([ft.Text(f"{APP} {__version__}", size=16, weight=ft.FontWeight.W_600),
                                         muted(f"Made by {APP_AUTHOR}. Free and open source.", size=13)],
                                        spacing=2, expand=True)], spacing=12),
        ft.Row([ft.OutlinedButton("Source code on GitHub", icon=ft.Icons.CODE_ROUNDED, url=APP_REPO)]),
        muted("Not affiliated with HoYoverse. Genshin Impact content and images belong to HoYoverse.", size=12),
        title="About")

    app.account_pick, app.account_row = account_pick, account_row
    return ft.Column([page_head(SETTINGS), prefs_card, phone_card, data_card, about_card], spacing=16,
                              horizontal_alignment=STRETCH)
