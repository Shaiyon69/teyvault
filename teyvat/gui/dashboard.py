"""Dashboard tab: account stats, today's domains, daily check-in rewards and promo codes."""
import datetime
import threading
import time

import flet as ft

from teyvat import background, db, hoyolab, vault, wiki
from teyvat.gui import endgame, theme
from teyvat.gui.theme import STRETCH
from teyvat.gui.widgets import bar, card, countdown, item_icon, label, muted, reward_tile, skeleton, today

PRIMOGEM_ICON = "https://cdn.jsdelivr.net/gh/MadeBaruna/paimon-moe@main/static/images/primogem.png"
REFRESH_S = 900  # real-time notes refresh (and alert check) while the app is open
_live = {}  # the newest window's load_resin; a theme change rebuilds the tab but keeps one refresh thread


def _watch():
    while True:
        time.sleep(REFRESH_S)
        try:
            _live["load"](quiet=True)
        except Exception:
            pass  # signed out, offline: the next round tries again


def build(app):
    page, phone, toast = app.page, app.phone, app.toast
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
            h -= 214 + (230 if endgame_card.visible else 0)  # head card, card padding, header row; endgame card + gap
            height = max(84, int(h / rows) - 6)  # NOTE: the endgame height is estimated; measure it if tiles overflow
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

    # Stats: resin, commissions, realm currency, expeditions, weekly bosses and the transformer, one card each,
    # 3 per row on PC (above the domains in the left column, so the rewards calendar gets the full height), 2 on phones.
    resin_strip = resin_card = ft.ResponsiveRow(spacing=16, run_spacing=16, visible=False)

    def stat_col():
        """Stat cards per row: 3 when the left column is wide enough for their labels, else 2."""
        return 6 if phone or (app.content_size()[0] - 16) / 2 < 600 else 4

    def load_resin(quiet=False):
        """Worker thread, after the game accounts are known. Real-time notes of the active account, and their
        alerts. `quiet`: the timed refresh, which keeps the old cards up instead of a skeleton."""
        role = active_role()
        resin_card.visible = role is not None
        dash_sub.value = (f"{role['nickname']} · AR {role['level']} · {role['region_name']}" if role
                          else "Sign in to HoYoLAB to see your account here.")
        load_primos()  # the ledger is per game account
        if not role:
            page.update()
            return
        if not quiet:
            resin_strip.controls = [ft.Container(skeleton(1, height=52), col=12)]
            page.update()
        try:
            n = hoyolab.daily_note(vault.load(), role)
        except Exception as ex:
            if quiet:
                return
            resin_strip.controls = [card(muted(f"Could not load resin: {ex}. Turn on Real-time Notes in "
                                               "HoYoLAB's Battle Chronicle settings.", size=13), col=12)]
        else:
            cur, cap, left = n["current_resin"], n["max_resin"], int(n["resin_recovery_time"])
            full = (datetime.datetime.now() + datetime.timedelta(seconds=left)).strftime("%a %H:%M")
            color = LOST if cur >= cap else ft.Colors.PRIMARY
            # compact cards: label and value on one line, a small note (or the resin bar) under it
            def stat(name, text, note, color=None):
                if phone:  # two narrow cards per row: label on its own line, the value under it
                    return card(ft.Column([
                        label(name, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(text, size=17, weight=ft.FontWeight.W_600, color=color),
                        note if isinstance(note, ft.Control) else muted(note, size=11, max_lines=1,
                                                                           overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, horizontal_alignment=STRETCH), col=stat_col(),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10))
                return card(ft.Column([
                    ft.Row([label(name, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS), ft.Text(text, size=15, weight=ft.FontWeight.W_600,
                                                              color=color)], spacing=6),
                    note if isinstance(note, ft.Control) else muted(note, size=11, max_lines=1, tooltip=note,
                                                                       overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=4, horizontal_alignment=STRETCH), col=stat_col(),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10))

            now = datetime.datetime.now(datetime.timezone.utc)
            daily, weekly = (countdown((t - now).total_seconds()) for t in wiki.next_resets(role["region"], now))
            back = sum(e.get("status") == "Finished" for e in n.get("expeditions") or [])
            tf = n.get("transformer") or {}
            rt = tf.get("recovery_time") or {}
            ready = "Ready" if rt.get("reached") else countdown(
                rt.get("Day", 0) * 86400 + rt.get("Hour", 0) * 3600 + rt.get("Minute", 0) * 60)
            resin_strip.controls = [
                stat("Original Resin", f"{cur}/{cap}",
                     ft.Row([bar(cur / cap, color, height=4), muted("Full" if left <= 0 else f"full {full}", size=11)],
                            spacing=6), color),
                stat("Commissions", f"{n['finished_task_num']}/{n['total_task_num']}", f"resets in {daily}"),
                stat("Realm currency", f"{n['current_home_coin']:,}", f"of {n['max_home_coin']:,}"),
                stat("Expeditions", f"{n['current_expedition_num']}/{n['max_expedition_num']}",
                     f"dispatched · {back} back" if back else "dispatched"),
                stat("Weekly bosses", f"{n.get('remain_resin_discount_num', 0)}/{n.get('resin_discount_num_limit', 3)}",
                     f"left · resets in {weekly}"),
                stat("Transformer", ready if tf.get("obtained") else "-",
                     "Parametric Transformer" if tf.get("obtained") else "not obtained yet",
                     WON if rt.get("reached") else None),
            ]
            conn = db.connect()
            if background.setting(conn, "alerts") and (news := background.new_alerts(conn, role["game_uid"], n)):
                toast(" ".join(news))
                if app.desktop:  # the window may be minimised; mobile only gets the snackbar
                    background.notify("Teyvault", "\n".join(news))
        page.update()
        if not quiet:  # the timed refresh leaves the endgame records alone (fetched once per account anyway)
            load_endgame(role)

    # Primogems: no API returns the balance, so the player types it in (e.g. before closing the game);
    # the saved counts are their ledger, each with the change since the one before.
    primo_text = ft.Text(color=GOLD, weight=ft.FontWeight.W_600)
    primo_btn = ft.TextButton(ft.Row([ft.Image(src=wiki.image(PRIMOGEM_ICON), width=20, height=20), primo_text],
                                     spacing=6, tight=True), tooltip="Primogems: tap to update")
    primo_field = ft.TextField(hint_text="Current primogems", keyboard_type=ft.KeyboardType.NUMBER,
                               border_radius=14, filled=True, dense=True, expand=True)
    primo_log = ft.Column(spacing=2)
    diary_col = ft.Column(spacing=6, horizontal_alignment=STRETCH)

    def load_diary():
        """Traveler's Diary (worker thread): this month's primogem and mora income by source."""
        role = active_role()
        if not role:
            return
        diary_col.controls = [skeleton(1, height=40)]
        diary_col.update()
        try:
            d = hoyolab.diary(vault.load(), role)
        except Exception as ex:
            diary_col.controls = [muted(f"Could not load the Traveler's Diary: {ex}", size=12)]
            diary_col.update()
            return
        m, day = d["month_data"], d["day_data"]
        sources = sorted((g for g in m.get("group_by", []) if g["num"]), key=lambda g: -g["num"])
        diary_col.controls = [
            label(f"Traveler's Diary · {datetime.date(2000, d['data_month'], 1):%B}"),
            ft.Row([muted("Primogems", size=12, expand=True), ft.Text(f"{m['current_primogems']:,}", color=GOLD,
                                                                      weight=ft.FontWeight.W_600)]),
            muted(f"Today {day['current_primogems']:,} · last month {m['last_primogems']:,}", size=12),
            ft.Row([muted("Mora", size=12, expand=True), ft.Text(f"{m['current_mora']:,}", weight=ft.FontWeight.W_600)]),
            muted(f"Today {day['current_mora']:,} · last month {m['last_mora']:,}", size=12),
            label("Primogems by source"),
            *[ft.Row([muted(g["action"], size=12, width=130), bar(g["percent"] / 100, GOLD, height=4),
                      muted(f"{g['num']:,}", size=12, width=56, text_align=ft.TextAlign.RIGHT)], spacing=8)
              for g in sources],
            label("Your balance log"),
        ]
        diary_col.update()

    def open_primos(e):
        diary_col.controls = []
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Primogems"), actions=[ft.TextButton("Close", on_click=lambda ev: page.pop_dialog())],
            content=ft.Container(ft.Column([
                diary_col,
                ft.Row([primo_field, ft.FilledTonalButton("Save", icon=ft.Icons.SAVE_ROUNDED,
                                                          on_click=guarded(save_primos))],
                       spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                primo_log], spacing=12, tight=True, scroll=ft.ScrollMode.AUTO), width=min(420, (page.width or 420) - 48))))
        if logged_in():
            page.run_thread(load_diary)

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

    primo_btn.on_click = open_primos
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
            # characters on the Characters tab's farming planner come first, and are named here
            plan = db.get_json(db.connect(), f"planner:{role['game_uid']}", {}) if role else {}
            planned = {p["name"] for p in plan.values()}
            due = sorted(planned & {n for m in mats for n, _ in m["items"]})
            if due:
                domains_sub.value += f" Your planner: {', '.join(due)}."
            farm["mats"], farm["planned"] = mats, planned
            show_domains()
        page.update()

    farm = {}  # today's materials, redrawn on resize

    def domain_icon_size(n):
        """Largest icon (32-72 px) at which n icons fit the card without scrolling (PC)."""
        if phone:
            return 38
        w, h = app.content_size()
        w = (w - 16) / 2 - 42 + 4  # the left column, minus card padding; +4 for the last icon's missing gap
        rows = -(-len(resin_strip.controls) * stat_col() // 12)
        stats = rows * 71 + 16 if resin_card.visible else 0  # one card row is 71 px, plus the gap below
        h -= 99 + 134 + stats  # head card, the card's own chrome, the stat cards
        return next((s for s in range(72, 32, -2) if -(-n // max(1, int(w // (s + 4)))) * (s + 4) <= h), 32)

    def show_domains():
        # just who can farm today, no material names: one wrapping block of icons per kind, one kind shown
        mats = farm.get("mats")
        if mats is None:
            return
        later = lambda x: x[0] not in farm.get("planned", ())  # planned characters first
        groups = [(key, kind, sorted(((n, r) for m in mats if m["kind"] == key for n, r in m["items"]), key=later))
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
    endgame_card, load_endgame, reset_endgame = endgame.build(app)
    today_locked = signin_prompt("Sign in to HoYoLAB to check in, see your rewards and redeem codes.")

    if phone:
        today_view = ft.Column([page_head(0, sub=dash_line, inline=True), resin_card, today_locked, rewards_card, domains_card,
                                endgame_card, redeem_card], spacing=16, horizontal_alignment=STRETCH)
    else:
        today_view = ft.Column([
            page_head(0, redeem_card, sub=dash_line, inline=True),
            ft.Row([
                ft.Column([resin_card, today_locked, domains_card], spacing=16, horizontal_alignment=STRETCH,
                          expand=True),
                ft.Column([rewards_card, endgame_card], spacing=16, horizontal_alignment=STRETCH, expand=True),
            ], spacing=16, expand=True, vertical_alignment=STRETCH),
        ], spacing=16, horizontal_alignment=STRETCH, expand=True)


    def show_auth(on):
        redeem_card.visible = on
        today_locked.visible = not on
        if not on:
            rewards_card.visible = resin_card.visible = False
            reset_endgame()

    def fit():
        if len(resin_strip.controls) > 1:  # not the skeleton or an error card
            for c in resin_strip.controls:
                c.col = stat_col()
        show_rewards()
        show_domains()

    if not phone:
        app.on_resize.append(fit)
    app.load_rewards, app.load_resin, app.load_domains = load_rewards, load_resin, load_domains
    _live["load"] = load_resin
    if not _live.get("thread"):
        _live["thread"] = threading.Thread(target=_watch, daemon=True)
        _live["thread"].start()
    app.do_checkin, app.show_checkin, app.show_auto_note = do_checkin, show_checkin, show_auto_note
    app.show_dashboard_auth = show_auth
    app.fit_dashboard = fit if not phone else lambda: None
    return today_view
