"""Wiki tab: HoYoLAB's wiki catalogue and paimon.moe achievements, with pages that open in the app."""
import flet as ft

from teyvat import db, wiki
from teyvat.gui import theme
from teyvat.gui.app import WIKI
from teyvat.gui.theme import ELEMENT_COLORS, STRETCH, STYLE
from teyvat.gui.widgets import (detail_dialog, detail_head, guide_view, loading_body, muted, panel_tile, pill, pill_select,
                                portrait, search_field, skeleton, skill_text, tab_view)


def build(app):
    page, phone, mobile, current = app.page, app.phone, app.mobile, app.current
    tile_grid, tile_col, tile_px, skel_tile = app.tile_grid, app.tile_col, app.tile_px, app.skel_tile
    page_head, guarded, filter_bar = app.page_head, app.guarded, app.filter_bar
    GOLD, PURPLE, WON, _ = theme.accents()

    # Public catalogue (HoYoLAB wiki + paimon.moe achievements), cached in SQLite for a week.
    WIKI_CATS = {"Characters": ft.Icons.PEOPLE_ROUNDED, "Weapons": ft.Icons.HARDWARE_ROUNDED,
                 "Artifacts": ft.Icons.DIAMOND_ROUNDED, "Enemies": ft.Icons.PEST_CONTROL_ROUNDED,
                 "Collectibles": ft.Icons.COLLECTIONS_ROUNDED, "Achievements": ft.Icons.EMOJI_EVENTS_ROUNDED}
    # NOTE: tiles rendered a page at a time as you scroll (fewer on phones); switch to a virtualized GridView if it lags
    WIKI_PAGE = 30 if phone else 60
    wiki_state = {"cat": "Characters", "items": [], "limit": WIKI_PAGE, "done": set()}
    wiki_search = search_field("Search", lambda e: show_wiki(reset=True))
    wiki_filters = ft.Row()
    wiki_sort = pill_select("Sort", [ft.DropdownOption("name", "Name"), ft.DropdownOption("rarity", "Rarity")],
                            "name", lambda e: show_wiki(reset=True))
    wiki_count = muted("")
    wiki_grid = ft.Column(spacing=12, horizontal_alignment=STRETCH)

    def wiki_dropdown(name, values, key):
        """Filter pill; the set changes with the category, so PC sizing is applied here, not by filter_bar."""
        d = pill_select(name, [ft.DropdownOption("All")] + [ft.DropdownOption(v) for v in values],
                        on_select=lambda e: show_wiki(reset=True), width=170 if phone else None)
        d.data, d.expand = key, not phone
        return d

    def wiki_tile(e, owned):
        r = wiki.rarity(e)
        return ft.Container(ft.Column([
            ft.Stack([portrait(e["icon"], r, tile_px, WIKI_CATS[wiki_state["cat"]]),
                      ft.Container(ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color=WON), right=-4, top=-4,
                                   visible=owned)], width=tile_px, height=tile_px, clip_behavior=ft.ClipBehavior.NONE),
            ft.Text(e["name"], size=12 if phone else 13, weight=ft.FontWeight.W_600, max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.CENTER),
            muted("★" * r, size=11, color=GOLD if r == 5 else PURPLE if r == 4 else None, visible=bool(r)),
        ], spacing=2 if phone else 4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=6 if phone else 8, border_radius=STYLE["radius"] - 4, bgcolor=STYLE["card_bg"],
            border=STYLE["border"], on_click=lambda ev: open_entry(e),
            # phones have no hover, so long tooltip text would only slow every redraw
            tooltip=None if mobile else e["desc"][:400] or e["name"], col=tile_col)

    def entry_view(d, roles=(), weapon_rarity=None, selected=0):
        """A wiki page rendered in the app: one tab per section (attributes, talents, constellations, ...),
        then the build guide for characters."""
        skill = skill_text() if wiki_state["cat"] == "Characters" else str  # artifact pieces stay whole
        tabs = []
        for sec in d["sections"]:
            blocks, facts = [], []
            for name, text, icon in sec["rows"] + [("", "", "")]:  # sentinel flushes the last facts grid
                if name and not icon and len(text) < 120:  # attribute line: label over value, in a grid
                    facts.append(panel_tile(muted(name.upper(), size=11, weight=ft.FontWeight.W_600),
                                            ft.Text(text, size=14, weight=ft.FontWeight.W_600, selectable=True),
                                            padding=10, col={"xs": 6, "md": 4}))
                    continue
                if facts:
                    blocks.append(ft.ResponsiveRow(facts, spacing=8, run_spacing=8))
                    facts = []
                if icon:  # talent, constellation, artifact piece
                    blocks.append(panel_tile(ft.Row([
                        ft.Container(ft.Image(src=wiki.image(icon), width=36, height=36,
                                              error_content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=20)),
                                     width=48, height=48, border_radius=24, alignment=ft.Alignment.CENTER,
                                     bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
                        ft.Column([ft.Text(name, size=15, weight=ft.FontWeight.W_600),
                                   ft.Text(skill(text), size=13, selectable=True, color=ft.Colors.ON_SURFACE_VARIANT)],
                                  spacing=4, expand=True),
                    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START), padding=14))
                elif text:  # set bonus, lore
                    blocks.append(panel_tile(ft.Text(name, size=14, weight=ft.FontWeight.W_600, visible=bool(name)),
                                             muted(text, size=13, selectable=True), padding=14))
            tabs.append((sec["title"], blocks))
        if d["desc"]:
            blurb = muted(d["desc"], italic=True, selectable=True)
            tabs = [(tabs[0][0], [blurb, *tabs[0][1]]), *tabs[1:]] if tabs else [("Overview", [blurb])]
        if roles:
            tabs.append(("Build guide", guide_view(roles, weapon_rarity)))
        return tab_view(tabs or [("Overview", [muted("This page has no details yet.")])], selected)

    def open_entry(e):
        """Wiki tile -> its page inside the app (fetched once, then read from the local cache)."""
        r, cat = wiki.rarity(e), wiki_state["cat"]
        tags = [v for vs in e["filters"].values() for v in vs if "★" not in v and not v[:1].isdigit()]
        accent = next((ELEMENT_COLORS[t] for t in tags if t in ELEMENT_COLORS), None)
        shown = {}

        def set_short(ev):
            db.set_meta(db.connect(), "short_skills", "1" if ev.control.selected[0] == "lite" else "0")
            if shown:
                tabs = body.content
                body.content = entry_view(**shown, selected=tabs.data or 0)
                body.update()
        is_char = cat == "Characters"
        actions = [
            ft.SegmentedButton(
                selected=["lite" if db.get_meta(db.connect(), "short_skills") == "1" else "full"],
                segments=[ft.Segment("full", label="Full"),
                          ft.Segment("lite", label="Lite", tooltip="First sentence of each talent and constellation")],
                show_selected_icon=False, on_change=set_short, visible=is_char and not phone),
            ft.IconButton(ft.Icons.MENU_BOOK_ROUNDED, tooltip="Guide on Genshin Track",
                          url=wiki.genshintrack_url(e["name"]), visible=is_char),
            ft.IconButton(ft.Icons.PLAY_CIRCLE_ROUNDED, tooltip="Video guides", url=wiki.video_url(e["name"]),
                          visible=is_char),
            ft.IconButton(ft.Icons.OPEN_IN_NEW_ROUNDED, tooltip="Open on HoYoLAB", url=wiki.WIKI_ENTRY_URL.format(e["id"]))]
        head = lambda art=None: detail_head(page, phone, e["icon"], r, e["name"], " · ".join(["★" * r] * bool(r) + tags),
                                            accent=accent, art=art, actions=actions, fallback=WIKI_CATS[cat])
        body = loading_body()
        detail_dialog(page, phone, head(), body)

        def load():
            try:
                d = wiki.entry(db.connect(), e["id"])
                wiki.cache_images([d["image"]] + [x[2] for sec in d["sections"] for x in sec["rows"] if x[2]])
                roles, rarity = [], {}
                if is_char:
                    try:
                        conn = db.connect()
                        roles = wiki.build_guide(conn, e["name"])
                        rarity = {w["name"]: wiki.rarity(w) for w in wiki.entries(conn, "Weapons")}
                    except Exception:
                        pass  # offline with no cached guides: the page still shows
                shown.update(d=d, roles=roles, weapon_rarity=rarity)
                body.content, body.padding = entry_view(**shown), 0
                if d["image"]:  # the splash art goes in the banner
                    body.parent.controls[0] = head(d["image"])
            except Exception as ex:
                body.content = muted(f"Could not load this page: {ex}")
            body.parent.update()
        page.run_thread(load)

    def achievement_row(a):
        def toggle(ev):
            db.set_done(db.connect(), a["id"], ev.control.value)
            (wiki_state["done"].add if ev.control.value else wiki_state["done"].discard)(a["id"])
            show_wiki()
        return ft.Container(ft.Row([
            ft.Checkbox(value=a["id"] in wiki_state["done"], on_change=toggle),
            ft.Column([ft.Text(a["name"], size=14, weight=ft.FontWeight.W_600),
                       muted(a["desc"], size=12)], spacing=2, expand=True),
            pill(f"{a['reward']} primos", GOLD), pill(f"v{a['ver']}") if a["ver"] else ft.Container(),
        ], spacing=10), padding=ft.Padding.symmetric(horizontal=10, vertical=6), border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH)

    def show_wiki(reset=False):
        if reset:
            wiki_state["limit"] = WIKI_PAGE
        cat, items = wiki_state["cat"], wiki_state["items"]
        q = (wiki_search.value or "").strip().lower()
        picks = {d.data: d.value for d in wiki_filters.controls if d.data and d.value != "All"}
        if cat == "Achievements":
            status = picks.pop("status", None)
            shown = [a for a in items if (q in a["name"].lower() or q in a["desc"].lower())
                     and picks.get("category") in (None, a["category"])
                     and (status is None or (a["id"] in wiki_state["done"]) == (status == "Done"))]
            done = [a for a in items if a["id"] in wiki_state["done"]]
            wiki_count.value = (f"{len(done):,} of {len(items):,} done · {sum(a['reward'] for a in done):,} primos "
                                f"earned · showing {len(shown):,}. Ticks are saved on this device.")
            wiki_grid.controls = [achievement_row(a) for a in shown[:wiki_state["limit"]]]
        else:
            shown = [e for e in items if (q in e["name"].lower() or q in e["desc"].lower())
                     and all(v in e["filters"].get(k, []) for k, v in picks.items())]
            shown.sort(key=lambda e: (-wiki.rarity(e), e["name"]) if wiki_sort.value == "rarity" else e["name"])
            owned = {c["name"] for c in app.roster["chars"]} if cat == "Characters" else set()
            wiki_count.value = f"{len(shown):,} of {len(items):,} {cat.lower()}. Tap one for details."
            wiki_grid.controls = [tile_grid([wiki_tile(e, e["name"] in owned) for e in shown[:wiki_state["limit"]]])]
        wiki_state["more"] = len(shown) > wiki_state["limit"]
        wiki_body.update()

    def on_page_scroll(e):
        """Infinite scroll: the next page of wiki tiles loads as the bottom comes into view."""
        if current["i"] == WIKI and wiki_state.get("more") and e.pixels >= e.max_scroll_extent - 600:
            wiki_state["limit"] += WIKI_PAGE
            show_wiki()

    def load_wiki(refresh=False):
        """Fetch (or read the cache of) the picked category, then rebuild its filter bar. Worker thread."""
        cat = wiki_state["cat"]
        wiki_count.value = f"Loading {cat.lower()}..."
        wiki_grid.controls = [skeleton(12, height=56) if cat == "Achievements" else skeleton(12 if phone else 18, tile=skel_tile)]
        wiki_body.update()
        conn = db.connect()
        try:
            items = wiki.achievements(conn, refresh) if cat == "Achievements" else wiki.entries(conn, cat, refresh)
        except Exception as ex:
            wiki_count.value, wiki_grid.controls = f"Could not load {cat.lower()}: {ex}", []
            wiki_body.update()
            return
        if cat != wiki_state["cat"]:  # user switched category while this was loading
            return
        wiki_state["items"] = items
        if cat == "Achievements":
            wiki_state["done"] = db.done_ids(conn)
            wiki_filters.controls = [
                wiki_sort, wiki_dropdown("Category", sorted({a["category"] for a in items}), "category"),
                wiki_dropdown("Status", ["Done", "To do"], "status")]
        else:
            wiki_filters.controls = [wiki_sort] + [wiki_dropdown(wiki.label(k), vs, k)
                                                   for k, vs in wiki.filters(items).items()]
        wiki_sort.visible = cat not in ("Achievements", "Enemies")
        show_wiki(reset=True)
        if cat != "Achievements":  # keep the catalogue's pictures for offline use
            page.run_thread(wiki.cache_images, [e["icon"] for e in items])
        if refresh:
            return f"{cat} updated."

    def pick_wiki_cat(cat):
        wiki_state["cat"] = wiki_cat.value = cat
        wiki_cat.leading_icon = WIKI_CATS[cat]
        wiki_search.value = ""
        page.run_thread(load_wiki)

    # Category bar: a full-width dropdown on phones, segmented pills across the page on PC.
    wiki_cat = ft.Dropdown(label="Category", value="Characters", leading_icon=WIKI_CATS["Characters"],
                           expand=True, dense=True, filled=True, border_radius=999,
                           fill_color=ft.Colors.SURFACE_CONTAINER_HIGH, border_width=0,
                           options=[ft.DropdownOption(k, k, leading_icon=i) for k, i in WIKI_CATS.items()],
                           on_select=lambda e: pick_wiki_cat(e.control.value))
    wiki_tabs = ft.SegmentedButton(selected=["Characters"], show_selected_icon=False, expand=True,
                                   segments=[ft.Segment(k, label=k, icon=i) for k, i in WIKI_CATS.items()],
                                   on_change=lambda e: pick_wiki_cat(e.control.selected[0]))
    wiki_refresh = ft.IconButton(ft.Icons.REFRESH_ROUNDED, tooltip="Download again",
                                 on_click=guarded(lambda: load_wiki(refresh=True)))
    wiki_bar = filter_bar([wiki_search, wiki_refresh], wiki_filters)
    if not phone:
        wiki_sort.width, wiki_sort.expand = None, True
    wiki_body = ft.Column([
        ft.Row([wiki_cat if phone else wiki_tabs]), wiki_bar,
        wiki_count, wiki_grid,
    ], spacing=12, horizontal_alignment=STRETCH)
    app.load_wiki, app.on_page_scroll = load_wiki, on_page_scroll
    return ft.Column([page_head(WIKI), wiki_body], spacing=16, horizontal_alignment=STRETCH)
