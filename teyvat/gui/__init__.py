"""Teyvault GUI. One Flet app for Windows, Android and iOS, built on the same core as the CLI.
main() sets the theme, builds each tab (one module per tab) and puts them in the navigation shell."""
import datetime

import flet as ft

from teyvat import db, wiki, wish
from teyvat.gui import account, characters, dashboard, events, settings, wiki_tab, wishes, world
from teyvat.gui.app import ACCOUNT, SECTIONS, SETTINGS, App
from teyvat.gui.dashboard import PRIMOGEM_ICON
from teyvat.gui.theme import (APP, APP_AUTHOR, APP_REPO, FONTS, PRYDWEN, SEEDS, STRETCH, STYLE, make_theme, use_palette,
                              use_style)
from teyvat.gui.widgets import logo_badge, muted, title_bar_for, today


def main(page: ft.Page, start=0):
    """Build the window. A theme change calls it again (app.restart) with the tab to reopen as `start`."""
    page.title = APP
    page.controls.clear()
    page.appbar = page.navigation_bar = None
    app = App(page)
    phone, mobile, desktop, current = app.phone, app.mobile, app.desktop, app.current
    conn0 = db.connect()
    theme = db.get_meta(conn0, "theme", "dark")
    style = db.get_meta(conn0, "style", "clean")
    seed = db.get_meta(conn0, "seed", next(iter(SEEDS)))
    app.prefs = theme, style, seed
    # The palette and style must be set before any control is built: cards read them once.
    light = theme == "light" or theme == "system" and page.platform_brightness == ft.Brightness.LIGHT
    use_palette(light)
    use_style(style, light, mobile)
    page.fonts = FONTS
    page.theme_mode = ft.ThemeMode.LIGHT if light else ft.ThemeMode.DARK
    page.theme, page.dark_theme = make_theme(style, True, seed), make_theme(style, False, seed)
    page.padding = 0
    if desktop:  # our own title bar (traffic lights on the right) instead of the OS one
        page.window.title_bar_hidden = True
        page.window.title_bar_buttons_hidden = True

    # In nav order. Settings needs the Wishes import/export actions, so it is built after it.
    views = [m.build(app) for m in (dashboard, events, wishes, world, characters, wiki_tab, account, settings)]
    toast, logged_in, ensure_loaded, wide_rail = app.toast, app.logged_in, app.ensure_loaded, app.wide_rail
    show_auth, refresh_stats, flow_regions = app.show_auth, app.refresh_stats, app.flow_regions
    status_dot, status_label = app.status_dot, app.status_label
    today_view, events_view = views[0], views[1]

    # PC and tablets: sidebar (lots of width). Phones: bottom bar (thumb reach) + app bar with the page title.
    # All tabs stay mounted (only visibility toggles) so background updates never hit a detached control.
    section_title = ft.Text(SECTIONS[0][0], size=20, weight=ft.FontWeight.BOLD)

    def select(i):
        current["i"] = i
        ensure_loaded(i)
        if i < len(nav.destinations):  # the phone bottom bar has no Settings; it keeps the last tab lit
            nav.selected_index = i
        section_title.value = SECTIONS[i][0]
        for j, v in enumerate(views):
            v.visible = j == i
        if not phone:
            content.visible = i > 1
        page.update()

    app.select = select
    status_chip = ft.Container(
        ft.Row([status_dot, status_label], spacing=6, tight=True),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6), border_radius=20,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, on_click=lambda e: select(ACCOUNT),
        tooltip="Account",
    )
    watermark = ft.Container(
        ft.Row([ft.Icon(ft.Icons.CODE_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                muted(f"Made by {APP_AUTHOR}", size=12)], spacing=6, tight=True),
        url=APP_REPO, tooltip=APP_REPO, padding=ft.Padding.symmetric(horizontal=8, vertical=4), border_radius=8)
    on_change = lambda e: select(e.control.selected_index)

    if phone:
        # Icons only (the label is the long-press tooltip), so the bar stays slim.
        nav = ft.NavigationBar(on_change=on_change, label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_HIDE,
                               height=64, destinations=[
            ft.NavigationBarDestination(icon=icon, selected_icon=sel, label=label)
            for label, icon, sel in SECTIONS[:ACCOUNT]])
        page.navigation_bar = nav
        page.appbar = ft.AppBar(title=section_title, bgcolor=ft.Colors.SURFACE, center_title=False,
                                actions=[ft.IconButton(ft.Icons.SETTINGS_OUTLINED, tooltip="Settings",
                                                       on_click=lambda e: select(SETTINGS)),
                                         ft.Container(status_chip, padding=ft.Padding.only(right=12))])
        body = ft.SafeArea(ft.Column(views, scroll=ft.ScrollMode.AUTO, spacing=16, on_scroll=app.on_page_scroll,
                                     scroll_interval=200, horizontal_alignment=STRETCH),
                           expand=True, minimum_padding=16)
        if STYLE["panel"]:  # no separate panel on phones: the whole page is the panel
            page.bgcolor = STYLE["panel"]
    else:
        brand = ft.Column([ft.Text(APP.upper(), size=24, font_family=STYLE["heading_font"]),
                           ft.Text(datetime.date.today().strftime("%a, %d %b").upper(), size=12)], spacing=0)
        logo = logo_badge(64)
        nav = ft.NavigationRail(
            on_change=on_change, selected_index=0, extended=True, min_extended_width=248,
            group_alignment=-0.85, bgcolor=ft.Colors.TRANSPARENT if STYLE["bg"] else ft.Colors.SURFACE_CONTAINER,
            indicator_color=STYLE["card_bg"] if STYLE["bg"] else None,
            indicator_shape=ft.RoundedRectangleBorder(radius=10) if STYLE["bg"] else None,
            leading=ft.Container(ft.Row([logo, brand], spacing=12),
                padding=ft.Padding.only(left=4, top=12, bottom=32)),
            trailing=ft.Container(ft.Column([status_chip, watermark], spacing=8,
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                  padding=ft.Padding.only(bottom=16)),
            pin_trailing_to_bottom=True,
            destinations=[ft.NavigationRailDestination(icon=icon, selected_icon=sel, label=label)
                          for label, icon, sel in SECTIONS])
        # the dashboard and events fit the window on their own; every other tab scrolls
        content = ft.Column(views[2:], scroll=ft.ScrollMode.AUTO, spacing=16, on_scroll=app.on_page_scroll,
                            scroll_interval=200, horizontal_alignment=STRETCH, expand=True)

        def fit_rail():
            """Labelled sidebar when wide; icons with labels underneath on a portrait tablet."""
            wide = wide_rail()
            nav.extended = wide
            nav.label_type = None if wide else ft.NavigationRailLabelType.ALL
            brand.visible = status_label.visible = watermark.visible = wide
        fit_rail()
        if STYLE["page_bg"]:
            nav.bgcolor = STYLE["card_bg"]
        views_col = ft.Column([today_view, events_view, content], spacing=0, expand=True)
        if STYLE["panel"]:  # Clean: a lighter rounded panel that bleeds off the right and bottom edges
            page.bgcolor = STYLE["bg"]
            panel = ft.Container(views_col, expand=True, bgcolor=STYLE["panel"], margin=ft.Margin.only(top=10),
                                 border_radius=ft.BorderRadius.only(top_left=24),
                                 padding=ft.Padding.only(left=29, top=23, right=29, bottom=23))
        else:
            panel = ft.Container(views_col, expand=True, padding=ft.Padding.only(top=8, right=32, bottom=16))
        body = ft.Row([nav, panel], spacing=0 if STYLE["panel"] else 32, expand=True,
                      vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        if desktop:
            body = ft.Column([title_bar_for(page), body], spacing=0, expand=True)
        if mobile:  # tablet: keep clear of the status and gesture bars
            body = ft.SafeArea(body, expand=True)

    def on_resize(e):
        if not phone and nav.extended != wide_rail():
            fit_rail()
        flow_regions(e)
        for fit in app.on_resize:
            fit()
        page.update()

    page.on_resize = on_resize

    def restart():
        """Apply a theme change: rebuild every control with the new colors (they copy them when built).
        NOTE: tabs refetch their data like at startup (a few sequential requests); keep the old views'
        state if theme flipping ever gets frequent."""
        main(page, current["i"])
    app.restart = restart
    # "Match system" follows the OS while the app runs.
    page.on_platform_brightness_change = (lambda e: restart()) if theme == "system" else None

    if STYLE["page_bg"]:  # Glass: everything floats over one gradient
        page.bgcolor = STYLE["page_bg"][1]
        body = ft.Container(body, expand=True, gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=STYLE["page_bg"]))
    for i, v in enumerate(views):
        v.visible = i == 0
    if not phone:
        content.visible = False
    show_auth()
    page.add(body)
    refresh_stats()
    if start:
        select(start)

    last = db.get_meta(db.connect(), "last_checkin")
    app.show_checkin(last)
    app.show_auto_note()
    page.update()

    def auto_checkin():
        if last == today() or not logged_in() or not app.auto_on():
            return
        try:
            toast(f"Daily check-in: {app.do_checkin()}")
        except Exception as ex:
            toast(f"Daily check-in failed: {ex}")

    def startup():
        # One request at a time, like a person using the website, never a burst.
        if start:  # theme change: the first run already refreshed and prefetched everything
            app.load_rewards()
            app.load_profiles()
            app.load_domains()
            return
        auto_checkin()
        # Newer standard 5★ list and meta tiers from the repo; tabs read PRYDWEN when they draw, so update it in place.
        wiki.refresh_data()
        PRYDWEN.update(wish.load_data("prydwen_tiers.json"))
        app.load_rewards()
        app.load_profiles()
        # Character/weapon catalogue (cached a week) gives wish portraits for releases paimon.moe lacks.
        try:
            for cat in ("Characters", "Weapons"):
                wiki.entries(db.connect(), cat)
            refresh_stats()
        except Exception:
            pass  # offline: paimon.moe icons and initials still work
        app.load_domains()
        # Keep every character/weapon portrait on the device, so wishes and banners show them offline.
        wiki.cache_images([*wiki.icon_urls(), PRIMOGEM_ICON])
        refresh_stats()  # redraw the wish history from the local copies
        # The rest of the Wiki tab (lists and icons), so it opens offline too. Of the pages a tile opens,
        # only characters are kept ahead of time; the others are fetched on first open.
        for cat in ("Artifacts", "Enemies", "Collectibles", "Achievements"):
            try:
                if cat == "Achievements":
                    wiki.achievements(db.connect())
                else:
                    wiki.cache_images(e["icon"] for e in wiki.entries(db.connect(), cat))
            except Exception:
                pass  # offline: whatever is cached stays
        try:
            conn = db.connect()
            wiki.cache_images(wiki.prefetch_entries(conn, [e["id"] for e in wiki.entries(conn, "Characters")]))
        except Exception:
            pass

    page.run_thread(startup)


def run():
    ft.run(main)
