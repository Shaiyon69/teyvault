"""What every tab shares: the page, the layout flags and the helpers built on them."""
import importlib.util

import flet as ft

from teyvat import db, vault
from teyvat.gui.theme import STRETCH, STYLE
from teyvat.gui.widgets import card, muted

# (label, icon, selected icon)
SECTIONS = [
    ("Dashboard", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD_ROUNDED),
    ("Events", ft.Icons.VIEW_TIMELINE_OUTLINED, ft.Icons.VIEW_TIMELINE_ROUNDED),
    ("Wishes", ft.Icons.AUTO_AWESOME_OUTLINED, ft.Icons.AUTO_AWESOME_ROUNDED),
    ("World", ft.Icons.MAP_OUTLINED, ft.Icons.MAP_ROUNDED),
    ("Characters", ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE_ROUNDED),
    ("Wiki", ft.Icons.MENU_BOOK_OUTLINED, ft.Icons.MENU_BOOK_ROUNDED),
    ("Account", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON_ROUNDED),
    ("Settings", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS_ROUNDED),
]
SETTINGS = len(SECTIONS) - 1  # mobile reaches it from the app bar, not the bottom bar
ACCOUNT = SETTINGS - 1  # mobile: the sign-in chip in the app bar
EVENTS, WISHES, WORLD, CHARACTERS, WIKI = 1, 2, 3, 4, 5


class App:
    """Shared state of one window. Each tab's build(app) also hangs on it the functions other tabs call
    (e.g. app.refresh_stats, app.load_resin), so no tab imports another; they are looked up when called."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.mobile = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
        self.desktop = not self.mobile and not page.web
        # Tablets (shortest side 600 dp or more) get the PC layout: sidebar, wide tiles, filter rows.
        # NOTE: decided once at startup; a foldable that unfolds mid-session keeps the phone layout until restart.
        self.phone = phone = self.mobile and min(page.width or 0, page.height or 0) < 600
        # Character/wiki tiles fill the row at any width (ResponsiveRow) instead of leaving a gap on the right.
        # Phones: three to a row, more in landscape. PC: 72 columns so window-size steps stay whole numbers
        # (the sidebar takes ~280 px, so e.g. a 1280 px window shows 9 per row).
        self.tile_cols = 12 if phone else 72
        self.tile_col = {"xs": 4, "sm": 3, "md": 2} if phone else {"xs": 36, "sm": 24, "md": 18, "lg": 12, "xl": 8, "xxl": 6}
        self.tile_px = 56 if phone else 72  # portrait size in character/wiki tiles
        self.skel_tile = 96 if phone else 112
        self.picker = ft.FilePicker()
        self.has_webview = importlib.util.find_spec("webview") is not None  # desktop only
        self.bound_roles = []  # game accounts on the HoYoLAB login, filled by load_profiles
        self.loaded, self.current = set(), {"i": 0}  # tabs whose data was fetched; the tab on screen
        self.on_resize = []  # tabs whose layout follows the window size; called on every resize

    def wide_rail(self):
        """Sidebar with labels when there's room; narrower windows and portrait tablets get the slim icon rail,
        so the content keeps its width."""
        return (self.page.width or 0) >= 1200

    def content_size(self):
        """Width and height the section views get: the window minus nav, title bar and panel padding.
        NOTE: estimated from the shell's fixed sizes (clean style); measure the panel if layouts start to overflow."""
        w, h = self.page.width or 1280, self.page.height or 720
        if self.phone:
            return w - 32, h - 64 - 56 - 32  # bottom bar, app bar, SafeArea padding
        return w - (313 if self.wide_rail() else 148), h - (62 if self.desktop else 26)

    def tile_grid(self, tiles):
        gap = 8 if self.phone else 10
        return ft.ResponsiveRow(tiles, columns=self.tile_cols, spacing=gap, run_spacing=gap)

    def filter_bar(self, row, panel):
        """Full-width search (plus any buttons), then the filter pills: one line that fills the width on PC,
        two to a row on phones."""
        panel.spacing = 8
        if self.phone:
            panel.wrap, panel.run_spacing = True, 8
            for d in panel.controls:
                d.width = self.pill_w()
        else:
            for d in panel.controls:
                d.width, d.expand = None, True
        return ft.Column([ft.Row(row, spacing=8), panel], spacing=8, horizontal_alignment=STRETCH)

    def pill_w(self):
        """Phone filter pill width: two per row."""
        return (self.content_size()[0] - 8) // 2

    def active_role(self):
        """The game account World/Characters show: the one picked in Settings, else the first."""
        uid = db.get_meta(db.connect(), "default_uid")
        return next((r for r in self.bound_roles if r["game_uid"] == uid), self.bound_roles[0] if self.bound_roles else None)

    @staticmethod
    def logged_in() -> bool:
        try:
            vault.load()
            return True
        except vault.NotLoggedIn:
            return False

    @staticmethod
    def auto_on() -> bool:
        return db.get_meta(db.connect(), "auto_checkin", "1") == "1"

    def ensure_loaded(self, i):
        """Fetch a tab's data the first time it is opened, not all at startup (fewer requests, faster
        first paint on phones). World/Characters wait until the game accounts are known, and so do
        Events and the Wishes banners when signed in (their times follow the account's server)."""
        if (i in self.loaded or i not in (EVENTS, WISHES, WORLD, CHARACTERS, WIKI)
                or (i in (WORLD, CHARACTERS) and not self.bound_roles)
                or (i in (EVENTS, WISHES) and not self.bound_roles and self.logged_in())):
            return
        self.loaded.add(i)
        if i in (EVENTS, WISHES, WIKI):
            self.page.run_thread({EVENTS: self.load_timeline, WISHES: self.load_banners, WIKI: self.load_wiki}[i])
        else:
            self.page.run_thread({WORLD: self.load_world, CHARACTERS: self.load_characters}[i], self.active_role())

    def page_head(self, i, *side, sub=None, inline=False):
        """Head card every section opens with: UPPERCASE title (+ `sub` line, text or a Text to update later; `inline`
        puts it beside the title so the card keeps its height). Companion cards (`side`) sit to its right on PC and
        drop below it on phones."""
        phone = self.phone
        title = ft.Text(SECTIONS[i][0].upper(), size=20 if phone else 26, font_family=STYLE["heading_font"])
        if isinstance(sub, str):
            sub = muted(sub, size=14 if phone else 16)
        if inline and isinstance(sub, ft.Text):  # one line, or it wraps and the card grows anyway
            sub.max_lines, sub.overflow = 1, ft.TextOverflow.ELLIPSIS
        body = (ft.Row([title, ft.Container(sub, expand=True)], spacing=12,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER) if inline else ft.Column([title, sub] if sub else [title], spacing=2))
        head = card(body,
                    padding=ft.Padding.symmetric(horizontal=21, vertical=16 if phone else 20),
                    alignment=ft.Alignment.CENTER_LEFT)
        if phone:
            return ft.Column([head, *side], spacing=12, horizontal_alignment=STRETCH)
        return ft.Row([ft.Container(head, expand=True), *side], spacing=16, vertical_alignment=STRETCH,
                      intrinsic_height=True)

    def signin_prompt(self, text):
        """Shown instead of actions that need a login, so nothing fails after the click."""
        return card(ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, color=ft.Colors.ON_SURFACE_VARIANT),
                            muted(text, expand=True)], spacing=12),
                    ft.Row([ft.FilledButton("Sign in", icon=ft.Icons.LOGIN_ROUNDED, on_click=lambda e: self.select(ACCOUNT))]))

    def toast(self, msg):
        self.page.show_dialog(ft.SnackBar(ft.Text(msg), show_close_icon=True))

    def guarded(self, fn):
        """Wrap a blocking action: disable the button while it runs, show result or error.
        Flet runs sync handlers on its event loop, so fn goes to a worker thread (else the UI and
        every other event, e.g. a dialog's Cancel, freeze until it returns); hence each action
        opens its own DB connection."""
        def handler(e):
            e.control.disabled = True
            e.control.update()

            def work():
                try:
                    msg = fn()
                except (Exception, SystemExit) as ex:
                    msg = str(ex) or type(ex).__name__
                finally:
                    e.control.disabled = False
                    e.control.update()
                if msg:
                    self.toast(msg)
            self.page.run_thread(work)
        return handler
