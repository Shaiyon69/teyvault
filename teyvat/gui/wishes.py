"""Wishes tab: sync, import/export, the current banners and pity/50-50 stats per pool."""
import datetime
import json
from pathlib import Path

import flet as ft

from teyvat import db, wiki, wish
from teyvat.gui import theme
from teyvat.gui.app import WISHES
from teyvat.gui.theme import ELEMENT_COLORS, STRETCH, STYLE
from teyvat.gui.widgets import (banner_tile, card, item_icon, muted, pill_tabs, pity_color, pity_meter, pull_chip,
                                skeleton)

POOL_TITLES = {"character": "Character Event", "weapon": "Weapon Event", "standard": "Standard",
               "chronicled": "Chronicled", "beginner": "Beginner"}
POOL_ICONS = {"character": ft.Icons.PERSON_ROUNDED, "weapon": ft.Icons.HARDWARE_ROUNDED,
              "standard": ft.Icons.STAR_ROUNDED, "chronicled": ft.Icons.HISTORY_EDU_ROUNDED,
              "beginner": ft.Icons.SCHOOL_ROUNDED}
RERUN_TOP = 12  # the rerun tracker's first tab: the longest waits
PRIMOS_PER_PULL = 160
HISTORY_CAP = 60  # chips a banner's history shows before "Show all"


def build(app):
    page, phone, mobile, picker = app.page, app.phone, app.mobile, app.picker
    active_role, bound_roles, guarded, toast, page_head = (app.active_role, app.bound_roles, app.guarded, app.toast,
                                                           app.page_head)
    GOLD, PURPLE, _, _ = theme.accents()

    url_field = ft.TextField(hint_text="Wish link (Sync pastes it from the clipboard)" if mobile else "Paste wish history link",
                             border_radius=14, filled=True,
                             prefix_icon=ft.Icons.LINK_ROUNDED)
    sync_status = muted("", visible=False)
    stats_view = ft.Column(spacing=16, horizontal_alignment=STRETCH)

    view = {"ranks": "5", "order": "new", "full": set()}  # which pulls the history shows, in what order, uncapped pools
    banners_row = ft.ResponsiveRow([skeleton(1, height=150)], spacing=16, run_spacing=16,
                                   vertical_alignment=ft.CrossAxisAlignment.START)
    banners_card = card(banners_row, title="Current banner")

    def load_banners():
        """Worker thread. Hidden if paimon.moe can't be reached and nothing is cached."""
        role = active_role()
        try:
            data = wiki.banners(db.connect())
            live = wiki.current_banners(data, role and role["region"])
        except Exception:
            banners_card.visible = False
            reruns_card.controls = [muted("Banner history needs paimon.moe; try again when online.")]
            page.update()
            return
        show_reruns(wiki.reruns(data, role and role["region"]))
        wiki.cache_images([wiki.banner_image(b) for _, b, _, _ in live]
                          + [wiki.icon_for(wiki.name_for(x)) for _, b, _, _ in live
                             for x in b.get("featured", [])[:6] + b.get("featuredRare", [])[:5]])
        banners_row.controls = [banner_tile(*t) for t in live]
        for b in banners_row.controls:  # two banners split the row in half instead of leaving a third empty
            b.col = {"xs": 12, "md": 12 if len(live) == 1 else 6, "xl": max(4, 12 // len(live))}
        banners_card.visible = bool(live)
        page.update()

    # Rerun tracker: every banner 5★, longest wait first, like paimon.moe's banner history.
    reruns_grid = ft.ResponsiveRow([skeleton(1, height=150)], spacing=8, run_spacing=8)
    reruns_tabs = ft.Container()
    reruns_card = ft.Column([muted("5★ characters by time since their last banner.", size=12), reruns_tabs,
                             reruns_grid], spacing=12, horizontal_alignment=STRETCH, visible=False)

    def show_reruns(rows):
        """Tabs: the longest waits, then one per element (from the wiki catalogue's cache, when there is one)."""
        try:
            element = {e["name"]: (e["filters"].get("character_vision") or [""])[0]
                       for e in wiki.entries(db.connect(), "Characters")}
        except Exception:
            element = {}
        tabs = {"top": rows[:RERUN_TOP], **{k: [r for r in rows if element.get(r["name"]) == k]
                                            for k in ELEMENT_COLORS if element}}

        def pick(key):
            fill_reruns(tabs[key])
            reruns_grid.update()
        reruns_tabs.content = pill_tabs([("top", "Longest wait", ft.Icons.HOURGLASS_BOTTOM_ROUNDED)]
                                        + [(k, k) for k, v in tabs.items() if k != "top" and v], pick)
        fill_reruns(tabs["top"])

    def fill_reruns(rows):
        now = datetime.datetime.now(datetime.timezone.utc)

        def when(r):
            if r["status"] == "live":
                return "On banner now", GOLD
            if r["status"] == "next":
                return "Coming next", GOLD
            return f"{(now - r['last']).days:,} days ago", None

        reruns_grid.controls = []
        for r in rows:
            text, color = when(r)
            reruns_grid.controls.append(ft.Container(ft.Row([
                item_icon(r["name"], "Character", 48),
                ft.Column([ft.Text(r["name"], size=13, weight=ft.FontWeight.W_600, no_wrap=True,
                                   overflow=ft.TextOverflow.ELLIPSIS),
                           ft.Text(text, size=12, color=color or ft.Colors.ON_SURFACE_VARIANT),
                           muted(f"{r['runs']} run{'s' * (r['runs'] != 1)}", size=11)], spacing=0, expand=True)],
                spacing=10), col={"xs": 6, "sm": 4, "md": 3, "xl": 2}))

    def set_view(key):
        def handler(e):
            view[key] = e.control.selected[0]
            refresh_stats()
        return handler

    rank_pick = ft.SegmentedButton(selected=[view["ranks"]], on_change=set_view("ranks"), show_selected_icon=False,
                                   segments=[ft.Segment("5", label="5★"), ft.Segment("4", label="4★"),
                                             ft.Segment("all", label="All")])
    order_pick = ft.SegmentedButton(selected=[view["order"]], on_change=set_view("order"), show_selected_icon=False,
                                    segments=[ft.Segment("new", label=ft.Text("Newest", no_wrap=True),
                                                         icon=ft.Icons.ARROW_DOWNWARD_ROUNDED),
                                              ft.Segment("old", label=ft.Text("Oldest", no_wrap=True),
                                                         icon=ft.Icons.ARROW_UPWARD_ROUNDED)])
    history_bar = ft.Row([rank_pick, order_pick], wrap=True, spacing=12, run_spacing=8,
                         vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def pool_card(pool, s):
        """Banner card laid out like paimon.moe's wish counter."""
        total, fives, fours, hard = s["total"], s["five_stars"], s["four_stars"], s["hard_pity"]
        pct = lambda n: f"{n / total:.2%}" if total else "-"
        avg = f"{sum(f['pity'] for f in fives) / len(fives):.1f}" if fives else "-"
        five_tip = f"{pct(len(fives))} · avg pity {avg}"
        if pool == "character":
            decided = s["won"] + s["lost"]
            five_tip += f"\n50/50: {s['won'] / decided:.0%} ({s['won']}W · {s['lost']}L)" if decided else ""
        counts = [total_chip("5★", str(len(fives)), five_tip, GOLD),
                  total_chip("4★", str(len(fours)), pct(len(fours)), PURPLE)]
        shown = {"5": fives, "4": s["four_stars"], "all": fives + s["four_stars"]}[view["ranks"]]
        shown = sorted(shown, key=lambda f: int(f["id"]), reverse=view["order"] == "new")
        # Hundreds of 4★ chips are slow to lay out (phones above all), so a long history opens capped.
        more = len(shown) - HISTORY_CAP if pool not in view["full"] else 0
        history = [pull_chip(f, hard) for f in (shown[:HISTORY_CAP] if more > 0 else shown)]
        if more > 0:
            history.append(ft.TextButton(f"Show all ({more:,} more)", on_click=lambda e: (view["full"].add(pool),
                                                                                         refresh_stats())))
        label = {"5": "5★", "4": "4★", "all": "5★ and 4★"}[view["ranks"]]
        # Full-width card per banner; the 5★ history runs full length below (no inner scroll),
        # so the card grows with the banner's pulls.
        return card(
            ft.Row([
                ft.Column([
                    ft.Row([ft.Icon(POOL_ICONS[pool], size=18, color=ft.Colors.PRIMARY),
                            ft.Text(POOL_TITLES[pool], size=16, weight=ft.FontWeight.W_600)], spacing=8, tight=True),
                    ft.Container(ft.Text("Next 5★ guaranteed", size=12, color=GOLD,
                                         weight=ft.FontWeight.W_600),
                                 padding=ft.Padding.symmetric(horizontal=6, vertical=1), border_radius=6,
                                 border=ft.Border.all(1, GOLD), visible=s["guaranteed"]),
                ], spacing=4, expand=True),
                ft.Column([ft.Text(f"{total:,}", size=22, weight=ft.FontWeight.BOLD),
                           muted(f"{total * PRIMOS_PER_PULL:,} primos", size=12)],
                          spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
            ], vertical_alignment=ft.CrossAxisAlignment.START, height=44),
            ft.Row([ft.Container(pity_meter("5★ Pity", s["pity"], hard, pity_color(s["pity"], hard)),
                                 expand=3),
                    ft.Container(pity_meter("4★ Pity", s["pity4"], 10, PURPLE), expand=2)], spacing=16),
            ft.Row([muted(f"{label} history · {'newest' if view['order'] == 'new' else 'oldest'} first", size=13,
                          expand=True),
                    *counts], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row(history, wrap=True, spacing=6, run_spacing=6) if history else muted(f"No {label} yet."),
            col=12,
        )

    # Lifetime totals sit inside the WISHES head card, right of the title: one-line chips no taller than the
    # title, so the card matches the other sections' heads. Details in the tooltip.
    wish_totals = ft.Row(spacing=8, alignment=ft.MainAxisAlignment.END, wrap=phone)

    def total_chip(name, value, tip, color=None):
        return ft.Container(
            ft.Row([muted(name, size=12), ft.Text(value, size=15, weight=ft.FontWeight.W_600, color=color)],
                   spacing=6, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=10, vertical=4), border_radius=STYLE["radius"] - 6,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, tooltip=tip)

    def overview(rows, pools):
        fives = sum(len(s["five_stars"]) for s in pools.values())
        return [
            total_chip("Lifetime pulls", f"{len(rows):,}", f"{fives} × 5★"),
            total_chip("Primogems spent", f"{len(rows) * PRIMOS_PER_PULL:,}", f"{PRIMOS_PER_PULL} per pull", GOLD),
        ]

    def refresh_stats():
        conn = db.connect()
        uids = db.uids(conn)
        uid_pick.visible = len(uids) > 1  # a picker with one choice is just noise
        wish_totals.controls = []
        if not uids:
            wish_totals.update()
            stats_view.controls = [card(
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=40, color=ft.Colors.PRIMARY),
                ft.Text("No wishes yet", size=16, weight=ft.FontWeight.W_600),
                muted("Use Sync above, or Import a file exported from another wish tracker."),
            )]
            stats_view.update()
            return
        default = active_role()["game_uid"] if bound_roles else None
        uid = next(u for u in (uid_pick.value, default, uids[-1]) if u in uids)
        uid_pick.options = [ft.DropdownOption(u, f"UID {u}") for u in uids]
        uid_pick.value = uid
        rows = db.wishes(conn, uid)
        pools = wish.stats(rows, wish.load_standard())
        wish_totals.controls = overview(rows, pools)
        wish_totals.update()
        # every banner stacked, one full-width card each, so History needs no second tab bar
        stats_view.controls = [history_bar, *(pool_card(p, st) for p, st in pools.items())]
        stats_view.update()

    uid_pick = ft.Dropdown(label="Account", leading_icon=ft.Icons.PERSON_ROUNDED, border_radius=14,
                           filled=True, dense=True, on_select=lambda e: refresh_stats())

    def log(msg):
        sync_status.value, sync_status.visible = msg.strip(), True
        sync_status.update()

    def do_sync():
        text = url_field.value.strip()
        if text:  # the copied text may carry more than the link (the in-game error page)
            url = wish.extract_gacha_url(text.encode())
            if not url:
                return "That is not a wish history link (it needs authkey=). See How to get the link."
        elif mobile:
            return "Copy your wish history link first (How to get the link), then tap Sync."
        else:
            url = wish.locate_gacha_url()
        added = wish.sync(db.connect(), url, log=log)
        refresh_stats()
        return f"Added {added} new wishes."

    async def do_import(e):
        files = await picker.pick_files(allowed_extensions=["json", "xlsx"], with_data=mobile)
        if not files:
            return
        f = files[0]
        try:
            raw = f.bytes if f.bytes is not None else Path(f.path).read_bytes()
            conn = db.connect()
            added = (wish.import_xlsx(conn, raw, active_role()["game_uid"] if bound_roles else None)
                     if f.name.lower().endswith(".xlsx")
                     else wish.import_uigf(conn, json.loads(raw)))
        except (Exception, SystemExit) as ex:  # the core reports bad files as SystemExit
            toast(f"Import failed: {ex}")
            return
        refresh_stats()
        toast(f"Imported {added} new wishes.")

    async def save(file_name, data):
        ext = file_name.rsplit(".", 1)[1]
        path = await picker.save_file(file_name=file_name, allowed_extensions=[ext], src_bytes=data)
        if path and not mobile:
            Path(path).write_bytes(data)
        if path:
            toast("Exported.")

    async def do_export(e):
        data = json.dumps(wish.export_uigf(db.connect()), ensure_ascii=False, indent=1).encode()
        await save("teyvault_wishes_uigf.json", data)

    async def do_export_xlsx(e):
        await save("teyvault_wishes.xlsx", wish.export_xlsx(db.connect()))

    # Desktop finds the link by itself, so the field is tucked behind a menu item; mobile has no other way in.
    url_field.visible = mobile
    clipboard = ft.Clipboard()
    sync_click = guarded(do_sync)

    async def mobile_sync(e):
        """Phones: an empty field is filled from the clipboard, so copying the link in game is the whole step."""
        if not url_field.value.strip():
            text = await clipboard.get() or ""
            if wish.extract_gacha_url(text.encode()):
                url_field.value = text.strip()
                url_field.update()
        sync_click(e)

    def link_guide(e):
        steps = [
            "Open Genshin Impact, then Wish > History, and wait until the list loads.",
            "Turn off Wi-Fi and mobile data.",
            "Tap Refresh / Retry on the history page. An error page shows a long link.",
            "Long-press the link, Select all, then Copy.",
            "Turn your internet back on, come back here and tap Sync. Teyvault reads the link from the clipboard.",
        ]
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Get your wish history link"),
            content=ft.Column([
                *[ft.Row([ft.Container(ft.Text(str(i), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                                       width=24, height=24, border_radius=12, alignment=ft.Alignment.CENTER,
                                       bgcolor=ft.Colors.PRIMARY),
                          ft.Text(t, size=14, expand=True)], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)
                  for i, t in enumerate(steps, 1)],
                muted("The link works for about a day; repeat these steps for the next sync. Teyvault only reads your "
                      "wish history with it, through the same page the game uses.", size=12),
            ], spacing=12, tight=True, scroll=ft.ScrollMode.AUTO, width=min(440, (page.width or 400) - 48)),
            actions=[ft.TextButton("Got it", on_click=lambda e: page.pop_dialog())]))

    def show_url_field(e):
        url_field.visible = True
        page.update()

    # One obvious action (Sync); rarely used file actions live behind one labelled menu.
    files_menu = ft.PopupMenuButton(
        content=ft.Container(
            ft.Row([ft.Icon(ft.Icons.IMPORT_EXPORT_ROUNDED, size=18), ft.Text("Import / Export"),
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, size=18)], spacing=6, tight=True),
            padding=ft.Padding.symmetric(horizontal=14, vertical=9), border_radius=20,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), alignment=ft.Alignment.CENTER),
        expand=True,
        items=[
            *([] if mobile else [ft.PopupMenuItem("Paste a link manually", icon=ft.Icons.LINK_ROUNDED,
                                                  on_click=show_url_field)]),
            ft.PopupMenuItem("Import file (UIGF JSON or Excel)", icon=ft.Icons.FILE_OPEN_ROUNDED, on_click=do_import),
            ft.PopupMenuItem("Export as UIGF JSON", icon=ft.Icons.SAVE_ALT_ROUNDED, on_click=do_export),
            ft.PopupMenuItem("Export as Excel", icon=ft.Icons.TABLE_VIEW_ROUNDED, on_click=do_export_xlsx),
        ])
    sync_steps = ("Copy your wish history link in game, then tap Sync (How to get the link), or receive your "
                  "history from Teyvault on PC (Settings > Phone sync)." if mobile else
                  "Open Wish > History in game once, then press Sync. Teyvault finds the link itself; it expires "
                  "after about a day.")
    uid_pick.width = None if phone else 170  # phones give it its own line, too narrow for one row
    # Companion card beside the head, one row like the Dashboard's redeem card; the how-to is the Sync tooltip.
    # Fixed width on PC like the redeem card: unexpanded in the head row, its stretched column would be unbounded.
    sync_card = card(
        ft.Row([ft.FilledButton("Sync", icon=ft.Icons.SYNC_ROUNDED, on_click=mobile_sync if mobile else sync_click,
                                 tooltip=None if mobile else sync_steps, expand=True),
                files_menu, *([] if phone else [uid_pick])], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        *([uid_pick] if phone else []), url_field,
        *([ft.TextButton("How to get the link", icon=ft.Icons.HELP_OUTLINE_ROUNDED, on_click=link_guide)] if mobile else []),
        sync_status, padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        width=None if phone else 420)

    # History | Rerun tracker: one page-level tab bar, the picked one shown in place of the other.
    def pick_section(key):
        stats_view.visible, reruns_card.visible = key == "history", key == "reruns"
        stats_view.update()
        reruns_card.update()
    section_tabs = pill_tabs([("history", "History", ft.Icons.HISTORY_ROUNDED),
                              ("reruns", "Rerun tracker", ft.Icons.UPDATE_ROUNDED)], pick_section)

    app.load_banners, app.refresh_stats, app.uid_pick = load_banners, refresh_stats, uid_pick
    app.do_import, app.do_export, app.do_export_xlsx = do_import, do_export, do_export_xlsx
    return ft.Column([
        page_head(WISHES, sync_card, sub=wish_totals, inline=True),
        banners_card,
        section_tabs,
        stats_view,
        reruns_card,
    ], spacing=16, horizontal_alignment=STRETCH)
