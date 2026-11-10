"""Dashboard Endgame card: Spiral Abyss, Imaginarium Theater and Stygian Onslaught at a glance, with the full
record (teams per floor/act/fight) in a dialog."""
import datetime

import flet as ft

from teyvat import hoyolab, vault, wiki
from teyvat.gui import theme
from teyvat.gui.theme import STRETCH
from teyvat.gui.widgets import card, detail_dialog, detail_head, label, muted, panel_tile, pill, portrait, skeleton, tab_view, tile

THEATER_DIFFICULTY = {1: "Easy", 2: "Normal", 3: "Hard", 4: "Visionary"}
ABYSS_RANKS = (("reveal_rank", "Most used"), ("defeat_rank", "Most defeats"), ("damage_rank", "Strongest hit"),
               ("take_damage_rank", "Most damage taken"))
MODES = {"abyss": ("Spiral Abyss", ft.Icons.CYCLONE_ROUNDED), "theater": ("Imaginarium Theater", ft.Icons.THEATER_COMEDY_ROUNDED),
         "onslaught": ("Stygian Onslaught", ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED)}
avatar_icon = lambda a: a.get("icon") or a.get("image") or a.get("avatar_icon")
# (uid, mode) -> response, kept for the session across theme rebuilds and the timed note refresh, so the
# records are fetched once per account, not every 15 minutes.
_cache = {}


def _avatars(x):
    """Every dict with an avatar icon anywhere inside a Battle Chronicle response (to prefetch the portraits)."""
    if isinstance(x, dict):
        if avatar_icon(x) and ("avatar_id" in x or "id" in x):
            yield x
        for v in x.values():
            yield from _avatars(v)
    elif isinstance(x, list):
        for v in x:
            yield from _avatars(v)


def _theater(d):
    return next((x for x in d.get("data", []) if x.get("has_data")), None)


def _onslaught(d):
    return next((x for x in d.get("data", []) if (x.get("single") or {}).get("has_data")), None)


def fetch(role):
    """Worker thread: the three records of this account, one request after another, each once per session.
    An empty Abyss cycle falls back to the previous one."""
    for mode, get in (("abyss", hoyolab.spiral_abyss), ("theater", hoyolab.theater), ("onslaught", hoyolab.onslaught)):
        key = (role["game_uid"], mode)
        if key in _cache:
            continue
        try:
            d = get(vault.load(), role)
            if mode == "abyss" and not d.get("floors"):
                d = {**hoyolab.spiral_abyss(vault.load(), role, previous=True), "previous": True}
        except Exception as ex:
            d = {"error": str(ex)}  # NOTE: cached too, so a failed mode retries only after sign-in or relaunch
        else:
            wiki.cache_images(avatar_icon(a) for a in _avatars(d))
        _cache[key] = d


def summary(mode, d):
    """(headline, note) for the card row; headline None = nothing to open."""
    if "error" in d:
        return None, f"Could not load: {d['error']}"
    if mode == "abyss":
        if not d.get("floors"):
            return None, "No run this cycle or the last"
        return f"{d['total_star']} ★", f"Floor {d['max_floor']}" + (" · previous cycle" if d.get("previous") else "")
    if mode == "theater":
        s = _theater(d)
        if not s:
            return None, "No run yet"
        st = s["stat"]
        diff = st.get("difficulty_id")
        return f"{st.get('medal_num', '-')} ★", f"Act {st.get('max_round_id', '-')} · {THEATER_DIFFICULTY.get(diff, diff or '-')}"
    s = _onslaught(d)
    if not s:
        return None, "No run yet"
    best = s["single"].get("best") or {}
    return f"{best.get('second', '-')} s", f"Difficulty {best.get('difficulty', '-')}"


def build(app):
    """-> (card, load(role), reset()). The card is hidden until load fills it."""
    page = app.page
    GOLD, PURPLE, WON, LOST = theme.accents()
    accent = {"abyss": PURPLE, "theater": GOLD, "onslaught": LOST}
    rows = ft.Column(spacing=4, horizontal_alignment=STRETCH)
    endgame_card = card(rows, title="Endgame", visible=False)

    def member(a, size):
        """Portrait with its level under it, like the in-game party screen."""
        return ft.Column([portrait(avatar_icon(a), a.get("rarity"), size, fade=False),
                          muted(f"Lv {a['level']}" if a.get("level") else "", size=11)],
                         spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def team(avatars, size=48):
        return ft.Row([member(a, size) for a in avatars], spacing=8, wrap=True, run_spacing=8)

    def stars(got, out_of, size=14):
        return ft.Row([ft.Icon(ft.Icons.STAR_ROUNDED, size=size, color=GOLD if i < got else ft.Colors.OUTLINE_VARIANT)
                       for i in range(out_of)], spacing=0, tight=True)

    def season(sched):
        start = sched.get("start_time")
        return datetime.datetime.fromtimestamp(int(start)).strftime("%B %Y") if start else ""

    def stat_row(*stats):
        return ft.ResponsiveRow([tile(n, str(v), color=c, col={"xs": 6, "md": 12 // len(stats)}) for n, v, c in stats],
                                spacing=8, run_spacing=8)

    def section(title, *controls):
        return ft.Column([label(title), *controls], spacing=8, horizontal_alignment=STRETCH)

    def abyss_tabs(d):
        ranks = [panel_tile(ft.Row([portrait(r[0]["avatar_icon"], r[0].get("rarity"), 44, fade=False),
                                    ft.Column([muted(name, size=12),
                                               ft.Text(f"{r[0]['value']:,}", size=16, weight=ft.FontWeight.W_600)],
                                              spacing=0)], spacing=12), col={"xs": 12, "sm": 6})
                 for key, name in ABYSS_RANKS if (r := d.get(key))]
        overview = [stat_row(("Stars", d["total_star"], GOLD), ("Deepest", d["max_floor"], PURPLE),
                             ("Battles", d["total_battle_times"], None), ("Wins", d["total_win_times"], WON))]
        if ranks:
            overview.append(section("Highlights", ft.ResponsiveRow(ranks, spacing=8, run_spacing=8)))
        tabs = [("Overview", overview)]
        for f in sorted(d["floors"], key=lambda f: -f["index"]):  # one tab per floor: a page builds only its own teams
            chambers = [panel_tile(
                ft.Row([ft.Text(f"Chamber {lv['index']}", size=15, weight=ft.FontWeight.W_600, expand=True),
                        stars(lv["star"], lv.get("max_star", 3))]),
                ft.ResponsiveRow([ft.Column([muted("First half" if b.get("index") == 1 else "Second half", size=12),
                                             team(b["avatars"])], spacing=6, col={"xs": 12, "sm": 6})
                                  for b in lv.get("battles", [])], spacing=12, run_spacing=10),
                padding=14) for lv in f["levels"]]
            tabs.append((f"Floor {f['index']} · {f['star']}/{f['max_star']}★", chambers or [muted("Not cleared.")]))
        return tabs

    def theater_tabs(d):
        s = _theater(d)
        st = s["stat"]
        diff = st.get("difficulty_id")
        acts = [panel_tile(
            ft.Row([ft.Text(f"Act {r['round_id']}", size=15, weight=ft.FontWeight.W_600, expand=True),
                    ft.Icon(ft.Icons.LOCAL_FLORIST_ROUNDED, size=18,
                            color=WON if r.get("is_get_medal") else ft.Colors.OUTLINE_VARIANT,
                            tooltip="Star earned" if r.get("is_get_medal") else "No star")]),
            team(r.get("avatars", [])), padding=14)
            for r in (s.get("detail") or {}).get("rounds_data", [])]
        return [("Overview", [stat_row(("Difficulty", THEATER_DIFFICULTY.get(diff, diff or "-"), PURPLE),
                                       ("Act reached", st.get("max_round_id", "-"), GOLD),
                                       ("Stars", st.get("medal_num", "-"), WON), ("Rentals", st.get("rent_cnt", "-"), None))]),
                ("Acts", acts or [muted("No act details.")])]

    def onslaught_tabs(d):
        single = _onslaught(d)["single"]
        best = single.get("best") or {}
        fights = [panel_tile(ft.Row([ft.Text(c.get("name", ""), size=15, weight=ft.FontWeight.W_600, expand=True),
                                     pill(f"{c.get('second', '-')} s", GOLD)]),
                             team(c.get("teams", [])), padding=14)
                  for c in single.get("challenge", [])]
        return [("Overview", [stat_row(("Difficulty", best.get("difficulty", "-"), PURPLE),
                                       ("Best time", f"{best.get('second', '-')} s", GOLD)),
                              *([section("Fights", *fights)] if fights else [])])]

    tabs_for = {"abyss": abyss_tabs, "theater": theater_tabs, "onslaught": onslaught_tabs}

    def sub_line(mode, d):
        if mode == "abyss":
            return season(d)
        s = _theater(d) if mode == "theater" else _onslaught(d)
        sched = s.get("schedule") or {}
        return (sched.get("name") if mode == "onslaught" else None) or season(sched)

    def open_mode(mode, d):
        name, icon = MODES[mode]
        head_text, note = summary(mode, d)
        face = next(_avatars(d), {})  # first character in the record (Abyss: most used) as the banner portrait
        head = detail_head(page, app.phone, avatar_icon(face), face.get("rarity"), name, sub_line(mode, d),
                           [pill(head_text, GOLD), pill(note)], accent=accent[mode], fallback=icon)
        detail_dialog(page, app.phone, head, ft.Container(tab_view(tabs_for[mode](d))))

    def row(mode, d):
        name, icon = MODES[mode]
        head, note = summary(mode, d)
        return ft.Container(ft.Row([
            ft.Icon(icon, size=20, color=PURPLE),
            ft.Column([ft.Text(name, size=14, weight=ft.FontWeight.W_600), muted(note, size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                      spacing=0, expand=True),
            ft.Text(head or "-", size=15, weight=ft.FontWeight.W_600, color=GOLD if head else None),
            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=18, color=ft.Colors.ON_SURFACE_VARIANT, opacity=1 if head else 0),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=8, vertical=6), border_radius=10, ink=bool(head),
            on_click=(lambda e: open_mode(mode, d)) if head else None)

    def load(role):
        """Worker thread, after the real-time notes (one request at a time)."""
        endgame_card.visible = True
        if any((role["game_uid"], m) not in _cache for m in MODES):
            rows.controls = [skeleton(3, height=40)]
            page.update()
            fetch(role)
        if (app.active_role() or {}).get("game_uid") != role["game_uid"]:  # account switched while loading: its own load redraws
            return
        rows.controls = [row(m, _cache[(role["game_uid"], m)]) for m in MODES]
        app.fit_dashboard()  # the reward calendar gives up the card's height
        page.update()

    def reset():
        _cache.clear()
        endgame_card.visible = False

    return endgame_card, load, reset
