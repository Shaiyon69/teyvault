"""World tab: exploration per region and account totals from Battle Chronicle, plus the live map links."""
import flet as ft

from teyvat import hoyolab, vault, wiki
from teyvat.gui import theme
from teyvat.gui.app import WORLD
from teyvat.gui.theme import STRETCH, STYLE
from teyvat.gui.widgets import bar, card, muted, skeleton, tile

# Battle Chronicle's own icon for these 404s or is empty, so the HoYoLAB wiki's emblem is used instead.
WIKI_STATIC = "https://act-webstatic.hoyoverse.com/event-static-hoyowiki-admin/"
WIKI_UGC = "https://act-upload.hoyoverse.com/event-ugc-hoyowiki/"
REGION_ICONS = {
    "Natlan": WIKI_UGC + "2024/08/31/237301566/8694aaf89d32e75eca416ec7fe41e487_8636855791292057309.png",
    "Ancient Sacred Mountain": WIKI_UGC + "2025/03/29/237301566/6fdb6cce9a5cce40096dce9c2672feba_7641303426493271828.png",
    "Nod-Krai": WIKI_UGC + "2025/09/20/237301566/78a8e1dd1bd89bf1cc3a54aaf005406f_9202701640283190184.png",
    "Windrest Peak": WIKI_STATIC + "2026/04/07/1ef18ac06790b8384d2bd592a26f9eaa_4294499528830036418.png",
    "Temple of Space": WIKI_STATIC + "2026/04/03/f074ef5535687601974bdcc973cd0a20_2383623952857545804.png",
}
region_icon = lambda w: REGION_ICONS.get(w["name"]) or w.get("icon") or w.get("inner_icon")
TEYVAT_GPS_URL = "https://www.teyvatgps.com/map"
HOYOLAB_MAP_URL = "https://act.hoyolab.com/ys/app/interactive-map/index.html"


def build(app):
    page, phone, mobile = app.page, app.phone, app.mobile
    page_head, signin_prompt = app.page_head, app.signin_prompt
    GOLD, PURPLE, WON, _ = theme.accents()

    # Links only: both maps run in the real browser (Teyvat GPS needs its screen sharing).
    hoyolab_map_btn = ft.OutlinedButton("HoYoLAB map", icon=ft.Icons.TRAVEL_EXPLORE_ROUNDED, url=HOYOLAB_MAP_URL)
    # Teyvat GPS needs screen sharing of the PC game window, so mobile only gets the official map.
    maps_card = card(
        muted("Official interactive map: tick off chests and oculi, saved to your HoYoLAB account.", size=13),
        ft.Row([hoyolab_map_btn]),
        title="Map",
    ) if mobile else card(
        muted("Teyvat GPS follows you live by reading your minimap through screen sharing. Lock the "
              "minimap to north (Settings > Others > Mini-map Settings > Fixed), share only the game "
              "window, then teleport to a waypoint so it can find you.", size=13),
        ft.FilledButton("Teyvat GPS", icon=ft.Icons.MY_LOCATION_ROUNDED, url=TEYVAT_GPS_URL), hoyolab_map_btn,
        title="Live map", width=None if phone else 260,
    )
    world_locked = signin_prompt("Sign in to HoYoLAB to see your exploration progress.")
    world_stats = ft.Column(spacing=16, horizontal_alignment=STRETCH)  # the two stat rows, filled by load_world
    world_body = ft.Column([world_locked], spacing=16, horizontal_alignment=STRETCH)
    # PC: the live map card runs down beside the head card and both stat rows
    world_view = ft.Column([page_head(WORLD), world_stats, maps_card, world_body], spacing=16,
                           horizontal_alignment=STRETCH) if phone else ft.Column([
        ft.Row([ft.Column([page_head(WORLD), world_stats], spacing=16, expand=True, horizontal_alignment=STRETCH),
                maps_card], spacing=16, vertical_alignment=ft.CrossAxisAlignment.START),
        world_body], spacing=16, horizontal_alignment=STRETCH)
    region_cards = []  # (estimated height, card), kept so a window resize can re-flow them
    region_grid = ft.Row(spacing=16, vertical_alignment=ft.CrossAxisAlignment.START)

    def flow_regions(e=None):
        """Masonry: each card drops into the currently shortest column, so tall regions leave no gaps."""
        n = max(1, min(4, int(app.content_size()[0] // 380)))
        if e and (len(region_grid.controls) == n or region_grid not in world_body.controls):
            return
        cols, heights = [[] for _ in range(n)], [0] * n
        for h, c in region_cards:
            i = heights.index(min(heights))
            cols[i].append(c)
            heights[i] += h
        region_grid.controls = [ft.Column(c, spacing=16, expand=True, horizontal_alignment=STRETCH)
                                for c in cols]
        if e:
            region_grid.update()


    def region_card(w, kids):
        """One region per card: big icon + completion on top, levels as pills, sub-areas listed below."""
        pct = w["exploration_percentage"] / 10
        color = WON if pct >= 100 else GOLD
        extras = [f"Statue Lv {w['seven_statue_level']}"] if w.get("seven_statue_level") else []
        if w["type"] == "Reputation" and w["level"]:
            extras.append(f"Reputation Lv {w['level']}")
        extras += [f"{o['name']} Lv {o['level']}" for o in w.get("offerings") or []]
        icon = region_icon(w)
        terrain = ft.Icon(ft.Icons.TERRAIN_ROUNDED, color=ft.Colors.ON_SURFACE_VARIANT)
        shown = bool(pct) or not kids  # a parent with 0% only groups its sub-areas
        head = ft.Row([
            # a region missing from REGION_ICONS whose API icon 404s still gets a glyph
            ft.Container(ft.Image(src=wiki.image(icon), width=40, height=40, error_content=terrain) if icon else terrain,
                         width=52, height=52, border_radius=14, alignment=ft.Alignment.CENTER,
                         bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH),
            ft.Text(w["name"], size=17, weight=ft.FontWeight.W_600, expand=True),
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color=WON, visible=pct >= 100),
                    ft.Text(f"{pct:g}%", size=22, weight=ft.FontWeight.BOLD, color=color)],
                   spacing=4, tight=True, visible=shown),
        ], spacing=12)
        body = [head]
        if shown:
            body.append(ft.Row([bar(pct / 100, color, height=8)]))
        if extras:
            body.append(ft.Row([ft.Container(muted(x, size=12), border_radius=999,
                                             padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                             bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH) for x in extras],
                               wrap=True, spacing=6, run_spacing=6))
        for k in kids:
            kp = k["exploration_percentage"] / 10
            kc = WON if kp >= 100 else GOLD
            body.append(ft.Column([
                ft.Row([ft.Text(k["name"], size=14, expand=True),
                        ft.Text(f"{kp:g}%", size=14, weight=ft.FontWeight.BOLD, color=kc)]),
                ft.Row([bar(kp / 100, kc, height=4)]),
            ], spacing=4))
        # NOTE: height estimated from row counts, measure rendered sizes if columns look uneven
        return 4 + bool(extras) + 1.5 * len(kids), card(*body)

    def load_world(role):
        """Battle Chronicle: exploration per region plus account totals (worker thread)."""
        world_stats.controls = [skeleton(2, height=96)]
        world_body.controls = [skeleton(3, height=180)]
        page.update()
        try:
            rec = hoyolab.game_record(vault.load(), role)
            wiki.cache_images(region_icon(w) for w in rec["world_explorations"])
        except Exception as ex:
            world_stats.controls = []
            world_body.controls = [card(muted(f"Could not load exploration: {ex}. Make sure Battle "
                                              "Chronicle is enabled in your HoYoLAB privacy settings."))]
            page.update()
            return
        st = rec["stats"]
        oculi = sum(v for k, v in st.items() if k.endswith("culus_number"))
        chests = sum(st[k] for k in ("common_chest_number", "exquisite_chest_number",
                                     "precious_chest_number", "luxurious_chest_number",
                                     "magic_chest_number"))
        regions = sorted(rec["world_explorations"], key=lambda w: w["id"])
        region_cards[:] = [region_card(w, [k for k in regions if k["parent_id"] == w["id"]])
                           for w in regions if not w["parent_id"]]
        flow_regions()
        # 12-column rows: four stats, then three (phones: two per row, the odd one out full width)
        stat = lambda name, value, color=None, wide=False, last=False: tile(
            name, value, color=color, raised=False, col={"xs": 12 if last else 6, "md": 4 if wide else 3})
        gap = 12 if phone else 16
        world_stats.controls = [
            ft.ResponsiveRow([
                stat("Days active", f"{st['active_day_number']:,}"),
                stat("Achievements", f"{st['achievement_number']:,}", GOLD),
                stat("Spiral Abyss", st["spiral_abyss"] or "-", PURPLE),
                stat("Oculi", f"{oculi:,}", WON),
            ], spacing=gap, run_spacing=gap),
            ft.ResponsiveRow([
                stat("Waypoints", f"{st['way_point_number']:,}", wide=True),
                stat("Domains", str(st["domain_number"]), wide=True),
                stat("Chests opened", f"{chests:,}", GOLD, wide=True, last=True),  # phones: no half-empty row
            ], spacing=gap, run_spacing=gap),
        ]
        world_body.controls = [
            ft.Row([ft.Text("MAP EXPLORATION", size=20 if phone else 24, font_family=STYLE["heading_font"]),
                    muted(role["nickname"])], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            region_grid,
        ]
        page.update()


    def reset():
        """Signed out: back to the sign-in prompt."""
        world_body.controls, world_stats.controls = [world_locked], []

    app.load_world, app.flow_regions, app.reset_world = load_world, flow_regions, reset
    return world_view
