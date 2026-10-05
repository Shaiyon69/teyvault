"""Characters tab: the account's roster with Prydwen meta tiers, filters, and each character's build."""
import flet as ft

from teyvat import db, hoyolab, vault, wiki, wish
from teyvat.gui import theme
from teyvat.gui.app import CHARACTERS
from teyvat.gui.theme import ELEMENT_COLORS, PRYDWEN, STRETCH, STYLE, TIER_COLORS
from teyvat.gui.widgets import (card, clean, crit_value, detail_dialog, detail_head, guide_view, label, loading_body,
                                meta_ratings, muted, panel_tile, pill, pill_select, portrait, search_field, skeleton,
                                skill_text, tab_view)

WEAPON_TYPES = {1: "Sword", 10: "Catalyst", 11: "Claymore", 12: "Bow", 13: "Polearm"}


def build(app):
    page, phone, mobile = app.page, app.phone, app.mobile
    tile_grid, tile_col, tile_px, skel_tile = app.tile_grid, app.tile_col, app.tile_px, app.skel_tile
    page_head, signin_prompt, filter_bar = app.page_head, app.signin_prompt, app.filter_bar
    GOLD, _, WON, _ = theme.accents()

    chars_locked = signin_prompt("Sign in to HoYoLAB to see your characters and their builds.")
    chars_body = ft.Column([chars_locked], spacing=16, horizontal_alignment=STRETCH)
    characters_view = ft.Column([page_head(CHARACTERS), chars_body], spacing=16, horizontal_alignment=STRETCH)
    builds = {}  # character id -> (detail, property_map); fetched on first open, one call per character

    roster = {"chars": [], "role": None, "release": {}}  # last loaded list, re-filtered without another request
    chars_count = muted("")
    chars_grid = ft.Column(spacing=12, horizontal_alignment=STRETCH)
    META_ROLES = ("On-field DPS", "Off-field DPS", "Support")

    def char_filter(name, options, width=150):
        return pill_select(name, [ft.DropdownOption("All")] + [ft.DropdownOption(k, v) for k, v in options],
                           on_select=lambda e: show_chars(), width=width)

    f_element = char_filter("Element", [(k, k) for k in ELEMENT_COLORS])
    f_weapon = char_filter("Weapon", [(v, v) for v in WEAPON_TYPES.values()])
    f_rarity = char_filter("Rarity", [("5", "5★"), ("4", "4★")], width=120)
    f_tier = char_filter("Meta tier", [(t, t) for t in PRYDWEN["tiers"]] + [("-", "Unrated")])
    f_role = char_filter("Meta role", [(r, r) for r in META_ROLES], width=170)
    f_sort = pill_select("Sort", [ft.DropdownOption("game", "HoYoLAB order"), ft.DropdownOption("tier", "Meta tier"),
                                  ft.DropdownOption("level", "Level"), ft.DropdownOption("release", "Release order")],
                         "game", lambda e: show_chars())
    f_group = pill_select("Group by", [ft.DropdownOption(k, v) for k, v in (
        ("none", "None"), ("element", "Element"), ("weapon", "Weapon"),
        ("rarity", "Rarity"), ("tier", "Meta tier"), ("role", "Meta role"))], "none", lambda e: show_chars())
    f_search = search_field("Search characters", lambda e: show_chars())
    chars_filters = filter_bar([f_search], ft.Row([f_element, f_weapon, f_rarity, f_tier, f_role, f_sort, f_group]))

    def show_chars():
        """Apply the filter bar to the loaded roster. Tier and role filters match the same rating, so
        "T0 + Support" only keeps characters Prydwen rates T0 as a support."""
        ranks = {t: i for i, t in enumerate(PRYDWEN["tiers"])}
        any_ = lambda d, v: d.value in ("All", v)

        def ratings(c):
            return [r for r in meta_ratings(c) if any_(f_role, r[1])]

        def meta_ok(c):
            if f_tier.value == "-":
                return not meta_ratings(c)
            return f_tier.value == f_role.value == "All" or any(any_(f_tier, t) for t, _ in ratings(c))

        q = (f_search.value or "").strip().lower()
        shown = [c for c in roster["chars"] if q in c["name"].lower()
                 and any_(f_element, c["element"]) and any_(f_weapon, WEAPON_TYPES.get(c["weapon_type"]))
                 and any_(f_rarity, str(c["rarity"])) and meta_ok(c)]
        if f_sort.value == "tier":
            shown.sort(key=lambda c: min((ranks[r[0]] for r in ratings(c)), default=len(ranks)))
        elif f_sort.value == "level":
            shown.sort(key=lambda c: -c["level"])
        elif f_sort.value == "release":  # oldest first; ones newer than paimon.moe's data go last
            slug = lambda n: "traveler" if n.lower().startswith("traveler") else wish.slug(n)
            shown.sort(key=lambda c: roster["release"].get(slug(c["name"]), "9999"))
        def best(c):  # top rating that passes the tier and role filters, or None
            return next((r for r in ratings(c) if any_(f_tier, r[0])), None)

        # group key per character, and the order groups appear in
        key, order = {
            "element": (lambda c: c["element"], list(ELEMENT_COLORS)),
            "weapon": (lambda c: WEAPON_TYPES.get(c["weapon_type"], "Other"), list(WEAPON_TYPES.values())),
            "rarity": (lambda c: f"{c['rarity']}★", ["5★", "4★"]),
            "tier": (lambda c: best(c)[0] if best(c) else "Unrated", PRYDWEN["tiers"] + ["Unrated"]),
            "role": (lambda c: best(c)[1] if best(c) else "Unrated", [*META_ROLES, "Unrated"]),
        }.get(f_group.value, (lambda c: "", [""]))
        groups = {k: [] for k in order}
        for c in shown:
            groups.setdefault(key(c), []).append(c)
        grid = lambda cs: tile_grid([char_tile(c, roster["role"]) for c in cs])
        chars_grid.controls = [ft.Column([
            ft.Row([ft.Text(k, size=16, weight=ft.FontWeight.W_600,
                            color=ELEMENT_COLORS.get(k) or TIER_COLORS.get(k)), muted(str(len(cs)))],
                   spacing=8, visible=bool(k)),
            grid(cs)], spacing=8, horizontal_alignment=STRETCH) for k, cs in groups.items() if cs]
        chars_count.value = (f"{len(shown)} of {len(roster['chars'])} characters · {roster['role']['nickname']}. "
                             f"Tap one to see its build. Meta tiers: Prydwen.gg, {PRYDWEN['updated']}.")
        chars_body.update()

    def char_tile(c, role):
        w = c["weapon"]
        badge = [ft.Container(pill(t, TIER_COLORS[t]), right=-6, top=-6) for t, _ in meta_ratings(c)[:1]]
        icon = 16 if phone else 20
        weapon = ft.Image(src=wiki.image(w["icon"]), width=icon, height=icon,
                          error_content=ft.Icon(ft.Icons.HARDWARE_ROUNDED, size=icon - 4))
        lv, refine = f"Lv {c['level']} · C{c['actived_constellation_num']}", f"R{w['affix_level']}"
        # Phones: level, constellation, weapon and refinement on one line to keep the tile short.
        info = ([ft.Row([weapon, muted(f"{lv} · {refine}", size=11)], spacing=2, tight=True)] if phone else
                [muted(lv, size=12), ft.Row([weapon, muted(refine, size=12)], spacing=2, tight=True)])
        return ft.Container(ft.Column([
            ft.Stack([portrait(c["icon"], c["rarity"], tile_px), *badge],
                     width=tile_px, height=tile_px, clip_behavior=ft.ClipBehavior.NONE),
            ft.Text(c["name"], size=12 if phone else 14, weight=ft.FontWeight.W_600, no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS, color=ELEMENT_COLORS.get(c["element"])),
            *info,
        ], spacing=2 if phone else 4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=6 if phone else 10, border_radius=STYLE["radius"] - 4, bgcolor=STYLE["card_bg"],
            border=STYLE["border"],
            tooltip=None if mobile else f"{c['name']} · {c['element']} · {w['name']}",
            on_click=lambda e: open_build(c, role), col=tile_col)

    def build_view(c, d, pm, roles, weapon_rarity):
        """Tabs: Overview (stats, weapon), Artifacts, Talents (talents, constellations), Build guide."""
        name = lambda p: pm.get(str(p["property_type"]), {}).get("name", "?").replace(" ", " ")
        color = ELEMENT_COLORS.get(c["element"], GOLD)
        skill = skill_text()
        icon_disc = lambda src, fallback, on=True: ft.Container(
            ft.Image(src=wiki.image(src), width=36, height=36, error_content=ft.Icon(fallback, size=20)),
            width=48, height=48, border_radius=24, alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.with_opacity(0.3 if on else 0.08, color))
        stats = [panel_tile(
            muted(name(p).upper(), size=11, weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(p["final"], size=18, weight=ft.FontWeight.BOLD),
            muted(f"{p['base']} + {p['add']}", size=11, visible=bool(p.get("add"))),
            padding=10, col={"xs": 6, "sm": 4, "md": 3}) for p in d["selected_properties"]]
        w = d["weapon"]
        weapon = panel_tile(ft.Row([portrait(w["icon"], w["rarity"], 64, ft.Icons.HARDWARE_ROUNDED), ft.Column([
            ft.Text(w["name"], size=16, weight=ft.FontWeight.W_600),
            ft.Row([pill(f"Lv {w['level']}"), pill(f"R{w['affix_level']}", GOLD)], spacing=6),
            muted(" · ".join(f"{name(p)} {p['final']}" for p in (w["main_property"], w.get("sub_property")) if p),
                  size=12),
        ], spacing=4, expand=True)], spacing=14), padding=14)
        sets = {}
        for r in d["relics"]:
            sets.setdefault(r["set"]["name"], [0, r["set"].get("affixes", [])])[0] += 1
        bonuses = [panel_tile(ft.Text(f"{k} ({n}pc)", size=14, weight=ft.FontWeight.W_600, color=WON),
                              *[muted(f"{a['activation_number']}-Piece: {clean(a['effect'])}", size=12)
                                for a in affixes if a["activation_number"] <= n], padding=14)
                   for k, (n, affixes) in sets.items() if n >= 2] or [muted("No set bonus.", size=12)]
        total_cv = sum(crit_value(r["sub_property_list"]) for r in d["relics"])
        relics = [panel_tile(ft.Row([portrait(r["icon"], r["rarity"], 48, ft.Icons.DIAMOND_ROUNDED), ft.Column([
            ft.Row([ft.Text(r["pos_name"], size=13, weight=ft.FontWeight.W_600, expand=True), pill(f"+{r['level']}")]),
            ft.Text(f"{name(r['main_property'])} {r['main_property']['value']}", size=14, weight=ft.FontWeight.W_600,
                    color=GOLD),
        ], spacing=2, expand=True)], spacing=10),
            *[ft.Row([muted(name(p), size=12, expand=True), ft.Text(p["value"], size=12, weight=ft.FontWeight.W_500)])
              for p in r["sub_property_list"]],
            ft.Row([pill(f"CV {crit_value(r['sub_property_list']):.1f}", GOLD)], alignment=ft.MainAxisAlignment.END),
            padding=12, col={"xs": 12, "sm": 6, "md": 4}) for r in d["relics"]]
        talents = [panel_tile(ft.Row([
            icon_disc(t["icon"], ft.Icons.BOLT_ROUNDED),
            ft.Column([ft.Text(t["name"], size=15, weight=ft.FontWeight.W_600),
                       ft.Text(skill(clean(t["desc"])), size=13, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)],
                      spacing=4, expand=True),
            ft.Container(ft.Text(str(t["level"]), size=20, weight=ft.FontWeight.BOLD, color=color), padding=ft.Padding.only(left=8)),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START), padding=14)
            for t in d["skills"] if t["skill_type"] == 1]
        cons = [panel_tile(ft.Row([
            icon_disc(k["icon"], ft.Icons.STAR_ROUNDED, k["is_actived"]),
            ft.Column([ft.Row([pill(f"C{k['pos']}", color if k["is_actived"] else None),
                               ft.Text(k["name"], size=14, weight=ft.FontWeight.W_600, expand=True)], spacing=8),
                       ft.Text(skill(clean(k["effect"])), size=13, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)],
                      spacing=4, expand=True),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START), padding=14, opacity=1 if k["is_actived"] else 0.5)
            for k in sorted(d.get("constellations", []), key=lambda k: k["pos"])]
        tabs = [
            ("Overview", [label("Stats"), ft.ResponsiveRow(stats, spacing=8, run_spacing=8), label("Weapon"), weapon]),
            ("Artifacts", [ft.Row([label("Set bonus", expand=True), pill(f"Crit Value {total_cv:.1f}", GOLD)]), *bonuses,
                           label("Pieces"), ft.ResponsiveRow(relics, spacing=8, run_spacing=8) if relics
                           else muted("No artifacts equipped.")]),
            ("Talents", talents),
            ("Constellations", cons),
        ]
        if roles:
            tabs.append(("Build guide", guide_view(roles, weapon_rarity)))
        return tab_view(tabs)

    def open_build(c, role):
        sub = f"{c['element']} · Lv {c['level']} · C{c['actived_constellation_num']} · Friendship {c['fetter']}"
        chips = [pill(f"{t} · {r}", TIER_COLORS[t]) for t, r in meta_ratings(c)]
        head = detail_head(page, phone, c["icon"], c["rarity"], c["name"], sub, chips,
                           accent=ELEMENT_COLORS.get(c["element"]), art=c.get("image"), actions=[
                ft.IconButton(ft.Icons.MENU_BOOK_ROUNDED, tooltip="Guide on Genshin Track",
                              url=wiki.genshintrack_url(c["name"]))])
        body = loading_body()
        detail_dialog(page, phone, head, body)

        def load():
            try:
                if c["id"] not in builds:
                    builds[c["id"]] = hoyolab.character_detail(vault.load(), role, c["id"])
                    d = builds[c["id"]][0]
                    wiki.cache_images([c.get("image"), d["weapon"]["icon"]]
                                      + [x["icon"] for k in ("constellations", "skills", "relics") for x in d.get(k) or []])
                roles, rarity = [], {}
                try:
                    conn = db.connect()
                    roles = wiki.build_guide(conn, c["name"])
                    rarity = {w["name"]: wiki.rarity(w) for w in wiki.entries(conn, "Weapons")}
                except Exception:
                    pass  # offline with no cached guides: the build still shows
                body.content, body.padding = build_view(c, *builds[c["id"]], roles, rarity), 0
            except Exception as ex:
                body.content = muted(f"Could not load build: {ex}")
            body.update()
        page.run_thread(load)

    def load_characters(role):
        """Character roster from Battle Chronicle (worker thread). Builds load per character on click."""
        chars_body.controls = [skeleton(1, height=48), skeleton(12, tile=skel_tile)]
        chars_body.update()
        try:
            chars = hoyolab.characters(vault.load(), role)
        except Exception as ex:
            chars_body.controls = [card(muted(f"Could not load characters: {ex}. Make sure Battle "
                                              "Chronicle is enabled in your HoYoLAB privacy settings."))]
            chars_body.update()
            return
        builds.clear()
        try:
            release = wiki.release_dates(wiki.banners(db.connect()))
        except Exception:
            release = {}  # offline with no cache: "Release order" keeps HoYoLAB's order
        roster.update(chars=chars, role=role, release=release)
        chars_body.controls = [chars_filters, chars_count, chars_grid]
        show_chars()
        # Roster shows right away (icons not cached yet load from the web); keep them for next time.
        page.run_thread(wiki.cache_images, [u for c in chars for u in (c["icon"], c["weapon"]["icon"])])

    def reset():
        """Signed out: back to the sign-in prompt."""
        chars_body.controls = [chars_locked]

    app.load_characters, app.roster, app.reset_chars = load_characters, roster, reset
    return characters_view
