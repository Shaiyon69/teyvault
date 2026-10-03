"""Teyvault GUI. One Flet app for Windows, Android and iOS, built on the same core as the CLI."""
import datetime
import importlib.metadata
import importlib.util
import json
import re
from importlib import resources
from pathlib import Path

import flet as ft

from teyvat import db, hoyolab, lansync, vault, weblogin, wiki, wish

APP = "Teyvault"
GOLD, PURPLE, WON, LOST = "#E6C07B", "#B58CF5", "#7BD4A8", "#F08A8A"
ELEMENT_COLORS = {"Pyro": "#F08A5D", "Hydro": "#5DB4F0", "Anemo": "#74D9C0", "Electro": "#B58CF5",
                  "Dendro": "#A5D65B", "Cryo": "#9FDDF0", "Geo": "#E6C07B"}
RARITY_BG = {5: ["#9C6B3A", "#C9965A"], 4: ["#5E4A8C", "#8A6CC0"], 3: ["#3E6A8C", "#5A93B5"],
             2: ["#3E7A5E", "#5AA07E"], 1: ["#5A5F70", "#7A8090"]}
WEAPON_TYPES = {1: "Sword", 10: "Catalyst", 11: "Claymore", 12: "Bow", 13: "Polearm"}
PRYDWEN = json.loads(resources.files("teyvat").joinpath("data/prydwen_tiers.json").read_text("utf-8"))
TIER_COLORS = dict(zip(PRYDWEN["tiers"], [LOST, "#F0A86A", GOLD, "#D9D46A", WON, "#5DB4F0", PURPLE, "#8A8FA8"]))
PRIMOS_PER_PULL = 160
TEYVAT_GPS_URL = "https://www.teyvatgps.com/map"
HOYOLAB_MAP_URL = "https://act.hoyolab.com/ys/app/interactive-map/index.html"
STRETCH = ft.CrossAxisAlignment.STRETCH
NIGHT = ft.ColorScheme(
    primary=GOLD, on_primary="#1B1608", secondary=PURPLE, surface="#0E1020", on_surface="#ECE8F4",
    on_surface_variant="#BDBAD0", surface_container="#171A2E", surface_container_high="#1F2340",
    surface_container_highest="#272C4F", outline_variant="#2C3155",
)
# Light theme: the pastel accents are unreadable on a light surface, so each gets a darker twin.
DAY_ACCENTS = ("#946A14", "#6E46C0", "#1E8A5A", "#C0392B")  # GOLD, PURPLE, WON, LOST
DAY_ELEMENTS = {"Pyro": "#C8501E", "Hydro": "#1F7AC0", "Anemo": "#1A9C80", "Electro": "#7E4CC9",
                "Dendro": "#5E8F1E", "Cryo": "#2C93B5", "Geo": "#A87A1C"}
DAY = ft.ColorScheme(
    primary=DAY_ACCENTS[0], on_primary="#FFFFFF", secondary=DAY_ACCENTS[1], surface="#F7F5FB",
    on_surface="#1B1A24", on_surface_variant="#55526A", surface_container="#EEEAF5",
    surface_container_high="#E5E0EF", surface_container_highest="#DBD5E8", outline_variant="#CFC8DF",
)
THEMES = {"dark": "Dark", "light": "Light", "system": "Match system"}
APP_AUTHOR = "Shaiyon69"  # shown in the sidebar and the About card
APP_REPO = "https://github.com/Shaiyon69/teyvault"
# NOTE: fonts load from jsDelivr (Google Fonts repo), so the very first offline launch falls back
# to Flutter's default font; bundle the TTFs in assets/ if that matters.
FONT_CDN = "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl"
FONTS = {"Inter": f"{FONT_CDN}/inter/Inter%5Bopsz,wght%5D.ttf", "Doto": f"{FONT_CDN}/doto/Doto%5BROND,wght%5D.ttf"}
STYLES = {"classic": "Classic", "material": "Material You", "glass": "Glass", "nothing": "Nothing"}
SEEDS = {"#E6C07B": "Gold", "#6750A4": "Violet", "#1F7AC0": "Ocean", "#1E8A5A": "Forest", "#C8501E": "Ember",
         "#C2185B": "Rose"}
NOTHING_RED = "#D71921"
NOTHING_DARK = ft.ColorScheme(
    primary=NOTHING_RED, on_primary="#FFFFFF", secondary="#FFFFFF", surface="#000000", on_surface="#FFFFFF",
    on_surface_variant="#9A9A9A", surface_container="#0B0B0B", surface_container_high="#161616",
    surface_container_highest="#222222", outline_variant="#2E2E2E",
)
NOTHING_LIGHT = ft.ColorScheme(
    primary=NOTHING_RED, on_primary="#FFFFFF", secondary="#000000", surface="#FFFFFF", on_surface="#000000",
    on_surface_variant="#5E5E5E", surface_container="#F6F6F6", surface_container_high="#EDEDED",
    surface_container_highest="#E2E2E2", outline_variant="#D6D6D6",
)
# How cards/heroes look per style; set once by use_style() before any control is built.
STYLE = {"name": "classic", "radius": 20, "card_bg": ft.Colors.SURFACE_CONTAINER, "border": None, "blur": None,
         "hero": ["#3A2F5C", "#1F2340"], "page_bg": None, "heading_font": None}
POOL_TITLES = {"character": "Character Event", "weapon": "Weapon Event", "standard": "Standard",
               "chronicled": "Chronicled", "beginner": "Beginner"}
COOKIE_HELP = (
    "1. Log in at hoyolab.com in a desktop browser, and open genshin.hoyoverse.com/en/gift once.\n"
    "2. Press F12, then Application > Cookies.\n"
    "3. Copy ltoken_v2, ltuid_v2 (hoyolab.com) and cookie_token_v2, account_id_v2 (hoyoverse.com).\n"
    "4. Paste them below as: ltoken_v2=...; ltuid_v2=...; cookie_token_v2=...; account_id_v2=..."
)
# (label, icon, selected icon, one-line "what is this page for")
SECTIONS = [
    ("Today", ft.Icons.TODAY_OUTLINED, ft.Icons.TODAY_ROUNDED, "Daily check-in and promo codes."),
    ("Wishes", ft.Icons.AUTO_AWESOME_OUTLINED, ft.Icons.AUTO_AWESOME_ROUNDED, "Your pity, 50/50 record and 5★ history."),
    ("World", ft.Icons.MAP_OUTLINED, ft.Icons.MAP_ROUNDED, "Exploration progress and interactive maps."),
    ("Characters", ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE_ROUNDED, "Your characters and their builds."),
    ("Wiki", ft.Icons.MENU_BOOK_OUTLINED, ft.Icons.MENU_BOOK_ROUNDED, "Every character, weapon, artifact, enemy and "
                                                              "achievement, searchable."),
    ("Account", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON_ROUNDED, "Your HoYoLAB sign-in and game accounts."),
    ("Settings", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS_ROUNDED, "Preferences, phone sync and your data."),
]


SETTINGS = len(SECTIONS) - 1  # mobile reaches it from the app bar, not the bottom bar
ACCOUNT = SETTINGS - 1  # mobile: the sign-in chip in the app bar
WORLD, CHARACTERS, WIKI = 2, 3, 4


def use_light_palette():
    """Swap the accent colors for their light-theme twins. Run before any control is built."""
    # NOTE: module globals, so one theme per process (a theme change needs a restart);
    # move accents into ColorScheme roles if the theme must switch live.
    global GOLD, PURPLE, WON, LOST
    GOLD, PURPLE, WON, LOST = DAY_ACCENTS
    ELEMENT_COLORS.update(DAY_ELEMENTS)
    TIER_COLORS.update(zip(PRYDWEN["tiers"], [LOST, "#B8641C", GOLD, "#8E8A12", WON, "#1F7AC0", PURPLE, "#5E6380"]))


def use_style(name, light, mobile):
    """Card/hero look for a theme style. Same one-per-process limit as use_light_palette."""
    glass_tint = ft.Colors.with_opacity(0.55 if light else 0.07, ft.Colors.WHITE)
    STYLE.update({
        "material": {"name": name, "radius": 28, "card_bg": ft.Colors.SURFACE_CONTAINER_HIGH, "hero": None},
        "glass": {"name": name, "radius": 22, "card_bg": glass_tint,
                  "border": ft.Border.all(1, ft.Colors.with_opacity(0.6 if light else 0.14, ft.Colors.WHITE)),
                  "blur": None if mobile else ft.Blur(18, 18),  # backdrop blur is costly on phones
                  "page_bg": ["#E9E2FF", "#F7F5FB", "#DDF2FF"] if light else ["#2A1B5C", "#0E1020", "#0B3346"]},
        "nothing": {"name": name, "radius": 12, "card_bg": ft.Colors.SURFACE,
                    "border": ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), "hero": None, "heading_font": "Doto"},
    }.get(name, {}))


def make_theme(style, light, seed):
    if style == "material":
        return ft.Theme(color_scheme_seed=seed, use_material3=True, font_family="Inter")
    scheme = (NOTHING_LIGHT if light else NOTHING_DARK) if style == "nothing" else DAY if light else NIGHT
    return ft.Theme(color_scheme=scheme, font_family="Inter")


def today() -> str:
    return datetime.date.today().isoformat()


def card(*controls, title=None, icon=None, **kw):
    head = [ft.Row([ft.Icon(icon, color=ft.Colors.PRIMARY, size=20),
                    ft.Text(title, size=16, weight=ft.FontWeight.W_600)], spacing=8)] if title else []
    return ft.Container(ft.Column(head + list(controls), spacing=12, horizontal_alignment=STRETCH),
                        **{"padding": 20, "border_radius": STYLE["radius"], "bgcolor": STYLE["card_bg"],
                           "border": STYLE["border"], "blur": STYLE["blur"], **kw})


def hero(content, **kw):
    """Highlight card. Classic/Glass: purple gradient, always dark-themed so its text stays readable in
    light mode too. Material You / Nothing: the style's own accent surface."""
    if STYLE["hero"] is None:
        accent = ft.Colors.PRIMARY_CONTAINER if STYLE["name"] == "material" else STYLE["card_bg"]
        return ft.Container(content, padding=24, border_radius=STYLE["radius"] + 4, bgcolor=accent,
                            border=ft.Border.all(1, ft.Colors.PRIMARY) if STYLE["name"] == "nothing" else None, **kw)
    return ft.Container(content, padding=24, border_radius=STYLE["radius"] + 4, theme=ft.Theme(color_scheme=NIGHT, font_family="Inter"),
                        theme_mode=ft.ThemeMode.DARK, border=STYLE["border"], blur=STYLE["blur"],
                        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                                   colors=STYLE["hero"]), **kw)


def muted(text, **kw):
    return ft.Text(text, **{"size": 14, "color": ft.Colors.ON_SURFACE_VARIANT, **kw})


def pity_color(pity, hard):
    """Green = early (lucky), gold = before soft pity, red = soft/hard pity."""
    ratio = pity / hard
    return WON if ratio < 0.5 else GOLD if ratio < 0.82 else LOST


def bar(value, color, height=6):
    return ft.ProgressBar(value=value, color=color, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                          bar_height=height, border_radius=height / 2, expand=True)


def pity_meter(label, pity, hard, color):
    return ft.Column([
        ft.Row([muted(label, expand=True), ft.Text(str(pity), size=16, weight=ft.FontWeight.BOLD,
                                                   color=color), muted(f"/ {hard}")], spacing=4),
        ft.Row([bar(pity / hard, color)]),
    ], spacing=6)


def tile(label, value, sub="", color=None, **kw):
    return ft.Container(ft.Column([
        muted(label, size=13),
        ft.Text(value, size=20, weight=ft.FontWeight.BOLD, color=color),
        muted(sub, size=12, visible=bool(sub)),
    ], spacing=2), padding=12, border_radius=STYLE["radius"] - 6, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, **kw)


def item_icon(name, item_type, size=36, rarity=5):
    """Character/weapon portrait on its rarity backdrop. HoYoLAB's wiki icon first (it has new releases
    on day one), then paimon.moe's, then the initial."""
    initial = ft.Text(name[:1], size=size / 2.4, weight=ft.FontWeight.BOLD)
    paimon = ft.Image(src=wish.icon_url(name, item_type), width=size, height=size, error_content=initial)
    src = wiki.icon_for(name)
    return ft.Container(
        ft.Image(src=src, width=size, height=size, error_content=paimon) if src else paimon,
        width=size, height=size, border_radius=size / 2, alignment=ft.Alignment.CENTER,
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                   colors=RARITY_BG[rarity]),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


def clean(text) -> str:
    """HoYoLAB rich text -> plain: drop <color> tags and {LINK#...} markers."""
    return re.sub(r"<[^>]+>|\{/?LINK[^}]*\}", "", text or "").replace(r"\n", "\n")


def reward_tile(day, award, claimed, current):
    """One day of the monthly check-in calendar, using HoYoLAB's own reward icon."""
    return ft.Container(ft.Column([
        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color=WON) if claimed else muted(f"Day {day}", size=12),
        ft.Image(src=award["icon"], width=36, height=36,
                 error_content=ft.Icon(ft.Icons.CARD_GIFTCARD_ROUNDED, color=ft.Colors.ON_SURFACE_VARIANT)),
        ft.Text(f"×{award['cnt']:,}", size=12, weight=ft.FontWeight.W_600),
    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=66, padding=6, border_radius=12, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        opacity=0.45 if claimed and not current else 1,
        border=ft.Border.all(2, WON if claimed else GOLD) if current else None,
        tooltip=f"Day {day}: {award['name']} ×{award['cnt']:,}" + (" (claimed)" if claimed else ""))


def portrait(src, rarity, size, fallback=ft.Icons.PERSON_ROUNDED):
    """Game icon on its rarity backdrop, like the in-game character list."""
    return ft.Container(ft.Image(src=src, width=size, height=size,
                                 error_content=ft.Icon(fallback, size=size / 2)),
                        width=size, height=size, border_radius=size / 4, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                                   colors=RARITY_BG.get(rarity, ["#4A5068", "#6B7290"])))


def pill(text, color=None):
    return ft.Container(ft.Text(text, size=12, color=color or ft.Colors.ON_SURFACE_VARIANT,
                                weight=ft.FontWeight.W_600),
                        border_radius=999, padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST)


def crit_value(props) -> float:
    """2 x CRIT Rate + CRIT DMG over artifact substats (property_type 20 / 22), the usual roll-quality score."""
    pct = lambda p: float(str(p["value"]).rstrip("%") or 0)
    return sum(2 * pct(p) if p["property_type"] == 20 else pct(p) for p in props if p["property_type"] in (20, 22))


def meta_ratings(c) -> list[list[str]]:
    """[[tier, role], ...] from Prydwen, best first. HoYoLAB calls every Traveler just "Traveler"."""
    name = f"Traveler {c['element']}" if c["name"] == "Traveler" else c["name"]
    return PRYDWEN["characters"].get(name, [])


def pull_chip(f, hard):
    """Compact history pill: icon, name, pity count, 50/50 tag (5★ only). Chips wrap side by side."""
    tag = {"won": ("W", WON), "lost": ("L", LOST), "guaranteed": ("G", GOLD)}.get(f["outcome"])
    five = f["rank"] == 5
    parts = [
        item_icon(f["name"], f["item_type"], size=24, rarity=f["rank"]),
        ft.Text(f["name"], size=13, weight=ft.FontWeight.W_600, no_wrap=True, color=None if five else PURPLE),
        ft.Text(str(f["pity"]), size=13, weight=ft.FontWeight.BOLD,
                color=pity_color(f["pity"], hard if five else 10)),
    ]
    if tag:
        parts.append(ft.Container(ft.Text(tag[0], size=11, weight=ft.FontWeight.BOLD, color=tag[1]),
                                  padding=ft.Padding.symmetric(horizontal=4), border_radius=4,
                                  border=ft.Border.all(1, tag[1])))
    return ft.Container(ft.Row(parts, spacing=6, tight=True), padding=ft.Padding.only(left=3, top=3, right=8, bottom=3),
        border_radius=999, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        tooltip=f"{f['name']} · {f['time'][:10]}")


def logo_badge(size=40):
    return ft.Container(ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, color="#1B1608", size=size * 0.55), width=size,
                        height=size, border_radius=size * 0.3, alignment=ft.Alignment.CENTER,
                        gradient=ft.LinearGradient(colors=[GOLD, "#C9965A"]))


def traffic_lights(page):
    """macOS-style window buttons, mirrored to the right edge: minimize, maximize, close (rightmost)."""
    async def close(e):
        await page.window.close()

    def minimize(e):
        page.window.minimized = True
        page.update()

    def maximize(e):
        page.window.maximized = not page.window.maximized
        page.update()

    lights = [(ft.Icons.REMOVE_ROUNDED, "#FEBC2E", "Minimize", minimize),
              (ft.Icons.ADD_ROUNDED, "#28C840", "Maximize", maximize),
              (ft.Icons.CLOSE_ROUNDED, "#FF5F57", "Close", close)]
    glyphs = [ft.Icon(icon, size=10, color="#5A2A00", visible=False) for icon, *_ in lights]

    def hover(e):  # like macOS, glyphs show on all three while the group is hovered
        for g in glyphs:
            g.visible = e.data in (True, "true")
        e.control.update()

    return ft.Container(ft.Row([
        ft.Container(g, width=14, height=14, border_radius=7, bgcolor=color, alignment=ft.Alignment.CENTER,
                     tooltip=tip, on_click=fn) for g, (_, color, tip, fn) in zip(glyphs, lights)
    ], spacing=8, tight=True), on_hover=hover, padding=ft.Padding.symmetric(horizontal=6, vertical=4))


def title_bar_for(page):
    """Replaces the OS title bar: drag anywhere on it, double-click to maximize."""
    return ft.Row([
        ft.WindowDragArea(ft.Container(muted(APP, size=12), height=36, alignment=ft.Alignment.CENTER_LEFT,
                                       padding=ft.Padding.only(left=16)), expand=True),
        ft.Container(traffic_lights(page), padding=ft.Padding.only(right=12)),
    ], spacing=0, height=36)


def main(page: ft.Page):
    page.title = APP
    conn0 = db.connect()
    theme = db.get_meta(conn0, "theme", "dark")
    style = db.get_meta(conn0, "style", "classic")
    seed = db.get_meta(conn0, "seed", next(iter(SEEDS)))
    mobile = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
    desktop = not mobile and not page.web
    light = theme == "light" or theme == "system" and page.platform_brightness == ft.Brightness.LIGHT
    if light:
        use_light_palette()
    use_style(style, light, mobile)
    page.fonts = FONTS
    page.theme_mode = ft.ThemeMode.LIGHT if light else ft.ThemeMode.DARK
    page.theme, page.dark_theme = make_theme(style, True, seed), make_theme(style, False, seed)
    page.padding = 0
    if desktop:  # our own title bar (traffic lights on the right) instead of the OS one
        page.window.title_bar_hidden = True
        page.window.title_bar_buttons_hidden = True
    picker = ft.FilePicker()
    has_webview = importlib.util.find_spec("webview") is not None  # desktop only
    bound_roles = []  # game accounts on the HoYoLAB login, filled by load_profiles

    def active_role():
        """The game account World/Characters show: the one picked in Settings, else the first."""
        uid = db.get_meta(db.connect(), "default_uid")
        return next((r for r in bound_roles if r["game_uid"] == uid), bound_roles[0] if bound_roles else None)

    loaded, current = set(), {"i": 0}  # tabs whose data was fetched; the tab on screen

    def ensure_loaded(i):
        """Fetch a tab's data the first time it is opened, not all at startup (fewer requests, faster
        first paint on phones). World/Characters wait until the game accounts are known."""
        if i in loaded or i not in (WORLD, CHARACTERS, WIKI) or (i != WIKI and not bound_roles):
            return
        loaded.add(i)
        if i == WIKI:
            page.run_thread(load_wiki)
        else:
            page.run_thread({WORLD: load_world, CHARACTERS: load_characters}[i], active_role())

    def page_head(i):
        """Desktop: big page title + purpose. Mobile: the app bar has the title, keep only the purpose."""
        label, _, _, purpose = SECTIONS[i]
        return ft.Column([ft.Text(label, size=28, weight=ft.FontWeight.BOLD, visible=not mobile,
                                  font_family=STYLE["heading_font"]),
                          muted(purpose)], spacing=2)

    def signin_prompt(text):
        """Shown instead of actions that need a login, so nothing fails after the click."""
        return card(ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, color=ft.Colors.ON_SURFACE_VARIANT),
                            muted(text, expand=True)], spacing=12),
                    ft.Row([ft.FilledButton("Sign in", icon=ft.Icons.LOGIN_ROUNDED, on_click=lambda e: select(ACCOUNT))]))

    def toast(msg):
        page.show_dialog(ft.SnackBar(ft.Text(msg), show_close_icon=True))

    def guarded(fn):
        """Wrap a blocking action: disable the button while it runs, show result or error.
        Sync handlers run on a worker thread, so each action opens its own DB connection."""
        def handler(e):
            e.control.disabled = True
            e.control.update()
            try:
                msg = fn()
            except (Exception, SystemExit) as ex:
                msg = str(ex) or type(ex).__name__
            finally:
                e.control.disabled = False
                e.control.update()
            if msg:
                toast(msg)
        return handler

    def logged_in() -> bool:
        try:
            vault.load()
            return True
        except vault.NotLoggedIn:
            return False

    # --- Today tab ----------------------------------------------------------
    checkin_icon = ft.Icon(ft.Icons.EVENT_AVAILABLE_ROUNDED, size=28, color=ft.Colors.ON_PRIMARY)
    checkin_title = ft.Text(size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
    checkin_detail = muted("")
    codes = ft.TextField(hint_text="One code per line", multiline=True, min_lines=3, max_lines=8,
                         border_radius=14, filled=True)
    redeem_results = ft.Column(spacing=6)

    checkin_btn = ft.FilledButton("Check in now", icon=ft.Icons.TOUCH_APP_ROUNDED)
    auto_on = lambda: db.get_meta(db.connect(), "auto_checkin", "1") == "1"
    auto_note = muted("")

    def show_auto_note():
        auto_note.value = ("Teyvault checks in for you once a day when the app opens." if auto_on()
                           else "Automatic check-in is off (Settings).")

    def show_checkin(last, result=None):
        done = last == today()
        checkin_icon.icon = ft.Icons.CHECK_ROUNDED if done else ft.Icons.EVENT_AVAILABLE_ROUNDED
        checkin_title.value = "Checked in today" if done else "Not checked in yet"
        checkin_detail.value = result or (f"Last check-in: {last}" if last else "No check-ins yet.")
        checkin_btn.visible = not done  # nothing to press once it's done

    def do_checkin():
        result = hoyolab.checkin(vault.load())
        db.set_meta(db.connect(), "last_checkin", today())
        show_checkin(today(), result)
        page.update()
        return result

    rewards_grid = ft.Row(wrap=True, spacing=8, run_spacing=8)
    rewards_sub = muted("")
    rewards_card = card(rewards_sub, rewards_grid, title="Daily rewards", icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
                        visible=False)

    def load_rewards():
        """Fill the reward calendar from HoYoLAB (runs on a worker thread)."""
        rewards_card.visible = logged_in()
        if rewards_card.visible:
            try:
                m = hoyolab.checkin_month(vault.load())
            except Exception as ex:
                rewards_sub.value, rewards_grid.controls = f"Could not load rewards: {ex}", []
            else:
                signed, done = m["signed"], m["today_done"]
                current = signed - 1 if done else signed
                rewards_grid.controls = [reward_tile(i + 1, a, i < signed, i == current and not m["error"])
                                         for i, a in enumerate(m["awards"])]
                rewards_sub.value = (f"Could not load your progress: {m['error']}" if m["error"] else
                                     f"{datetime.date.today():%B}: {signed} of {len(m['awards'])} claimed")
                if done:  # trust the server, e.g. checked in from another device
                    db.set_meta(db.connect(), "last_checkin", today())
                    show_checkin(today())
        page.update()

    def do_checkin_and_refresh():
        result = do_checkin()
        load_rewards()
        return result

    def do_redeem():
        todo = [c for c in codes.value.split() if c]
        if not todo:
            return "Enter at least one code."
        redeem_results.controls = [muted(f"Redeeming {len(todo)} code(s), ~6s each...")]
        redeem_results.update()
        results = hoyolab.redeem(vault.load(), todo)
        redeem_results.controls = [
            ft.Row([ft.Text(c, weight=ft.FontWeight.W_600, font_family="monospace"), muted(r)],
                   wrap=True) for c, r in results]
        redeem_results.update()

    checkin_btn.on_click = guarded(do_checkin_and_refresh)
    checkin_hero = hero(ft.Column([
        ft.Row([
            ft.Container(checkin_icon, width=52, height=52, border_radius=26, bgcolor=ft.Colors.PRIMARY,
                         alignment=ft.Alignment.CENTER),
            ft.Column([checkin_title, checkin_detail], spacing=2, expand=True),
        ], spacing=16),
        auto_note,
        ft.Row([checkin_btn]),
    ], spacing=12, horizontal_alignment=STRETCH))
    redeem_card = card(muted("Paste codes from livestreams or events. One per line."), codes,
                       ft.Row([ft.FilledTonalButton("Redeem", icon=ft.Icons.REDEEM_ROUNDED,
                                                    on_click=guarded(do_redeem))]),
                       redeem_results, title="Redeem codes", icon=ft.Icons.CARD_GIFTCARD_ROUNDED)
    today_locked = signin_prompt("Sign in to HoYoLAB to check in, see your rewards and redeem codes.")

    # Desktop: actions on the left, the reward calendar beside them. Mobile: one column, actions first.
    today_view = ft.Column([
        page_head(0),
        ft.ResponsiveRow([
            ft.Column([checkin_hero, today_locked, redeem_card], spacing=16, horizontal_alignment=STRETCH,
                      col={"xs": 12, "lg": 5}),
            ft.Column([rewards_card], horizontal_alignment=STRETCH, col={"xs": 12, "lg": 7}),
        ], spacing=16, run_spacing=16, vertical_alignment=ft.CrossAxisAlignment.START),
    ], spacing=16, horizontal_alignment=STRETCH)

    # --- Wishes tab ---------------------------------------------------------
    url_field = ft.TextField(hint_text="Paste wish history link", border_radius=14, filled=True,
                             prefix_icon=ft.Icons.LINK_ROUNDED)
    sync_status = muted("", visible=False)
    stats_view = ft.Column(spacing=16, horizontal_alignment=STRETCH)

    view = {"ranks": "5", "order": "new"}  # which pulls the history shows, and in what order

    def set_view(key):
        def handler(e):
            view[key] = e.control.selected[0]
            refresh_stats()
        return handler

    rank_pick = ft.SegmentedButton(selected=[view["ranks"]], on_change=set_view("ranks"), show_selected_icon=False,
                                   segments=[ft.Segment("5", label="5★"), ft.Segment("4", label="4★"),
                                             ft.Segment("all", label="All")])
    order_pick = ft.SegmentedButton(selected=[view["order"]], on_change=set_view("order"), show_selected_icon=False,
                                    segments=[ft.Segment("new", label="Newest", icon=ft.Icons.ARROW_DOWNWARD_ROUNDED),
                                              ft.Segment("old", label="Oldest", icon=ft.Icons.ARROW_UPWARD_ROUNDED)])
    history_bar = ft.Row([muted("History", size=13), rank_pick, order_pick], wrap=True, spacing=12, run_spacing=8,
                         vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def pool_card(pool, s):
        """Banner card laid out like paimon.moe's wish counter."""
        total, fives, fours, hard = s["total"], s["five_stars"], s["four_stars"], s["hard_pity"]
        pct = lambda n: f"{n / total:.2%}" if total else "-"
        avg = f"{sum(f['pity'] for f in fives) / len(fives):.1f}" if fives else "-"
        tiles = [tile("5★", str(len(fives)), f"{pct(len(fives))} · avg {avg}", GOLD, expand=True),
                 tile("4★", str(len(fours)), pct(len(fours)), PURPLE, expand=True)]
        if pool == "character":
            decided = s["won"] + s["lost"]
            rate = f"{s['won'] / decided:.0%}" if decided else "-"
            tiles.append(tile("50/50", rate, f"{s['won']}W · {s['lost']}L", WON, expand=True))
        shown = {"5": fives, "4": s["four_stars"], "all": fives + s["four_stars"]}[view["ranks"]]
        shown = sorted(shown, key=lambda f: int(f["id"]), reverse=view["order"] == "new")
        history = [pull_chip(f, hard) for f in shown]
        label = {"5": "5★", "4": "4★", "all": "5★ and 4★"}[view["ranks"]]
        # Full-width card per banner; the 5★ history runs full length below (no inner scroll),
        # so the card grows with the banner's pulls.
        return card(
            ft.Row([
                ft.Column([
                    ft.Text(POOL_TITLES[pool], size=16, weight=ft.FontWeight.W_600),
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
            ft.Row(tiles, spacing=8),
            muted(f"{label} history · {'newest' if view['order'] == 'new' else 'oldest'} first", size=13),
            ft.Row(history, wrap=True, spacing=6, run_spacing=6) if history else muted(f"No {label} yet."),
            col=12,
        )

    def overview(rows, pools):
        fives = sum(len(s["five_stars"]) for s in pools.values())
        char = pools.get("character", {"won": 0, "lost": 0})
        return ft.ResponsiveRow([
            tile("Lifetime pulls", f"{len(rows):,}", col={"xs": 6, "md": 3}),
            tile("Primogems spent", f"{len(rows) * PRIMOS_PER_PULL:,}", color=GOLD, col={"xs": 6, "md": 3}),
            tile("5★ pulled", str(fives), color=GOLD, col={"xs": 6, "md": 3}),
            tile("50/50 record", f"{char['won']}W · {char['lost']}L", color=WON, col={"xs": 6, "md": 3}),
        ], spacing=8, run_spacing=8)

    def refresh_stats():
        conn = db.connect()
        uids = db.uids(conn)
        uid_pick.visible = len(uids) > 1  # a picker with one choice is just noise
        if not uids:
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
        stats_view.controls = [
            overview(rows, pools),
            history_bar,
            ft.ResponsiveRow([pool_card(p, s) for p, s in pools.items()], spacing=16, run_spacing=16),
        ]
        stats_view.update()

    uid_pick = ft.Dropdown(label="Account", leading_icon=ft.Icons.PERSON_ROUNDED, border_radius=14,
                           filled=True, dense=True, on_select=lambda e: refresh_stats())

    def log(msg):
        sync_status.value, sync_status.visible = msg.strip(), True
        sync_status.update()

    def do_sync():
        url = url_field.value.strip()
        if not url:
            if mobile:
                return "Paste a wish history link, or import a file exported from the PC app."
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

    # One obvious action (Sync); rarely used file actions live behind one labelled menu.
    files_menu = ft.PopupMenuButton(
        content=ft.Container(
            ft.Row([ft.Icon(ft.Icons.IMPORT_EXPORT_ROUNDED, size=18), ft.Text("Import / Export"),
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, size=18)], spacing=6, tight=True),
            padding=ft.Padding.symmetric(horizontal=14, vertical=9), border_radius=20,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)),
        items=[
            ft.PopupMenuItem("Import file (UIGF JSON or Excel)", icon=ft.Icons.FILE_OPEN_ROUNDED, on_click=do_import),
            ft.PopupMenuItem("Export as UIGF JSON", icon=ft.Icons.SAVE_ALT_ROUNDED, on_click=do_export),
            ft.PopupMenuItem("Export as Excel", icon=ft.Icons.TABLE_VIEW_ROUNDED, on_click=do_export_xlsx),
        ])
    sync_steps = (muted("Paste a wish history link and press Sync, or receive your history from "
                        "Teyvault on PC (Settings > Phone sync).") if mobile
                  else muted("Open Wish > History in game once, then press Sync. Teyvault finds the link "
                             "itself; it expires after about a day."))
    # Desktop finds the link by itself, so the field is tucked away; mobile has no other way in.
    url_field.visible = mobile

    def show_url_field(e):
        url_field.visible, e.control.visible = True, False
        page.update()

    link_input = ft.Column([url_field, ft.TextButton("Paste a link manually", icon=ft.Icons.LINK_ROUNDED,
                                                     on_click=show_url_field, visible=not mobile)],
                           horizontal_alignment=ft.CrossAxisAlignment.START)
    # One slim bar instead of a tall card: how-to, account picker and actions share a row.
    uid_pick.width = 220
    # No expand= inside a wrap Row: Flutter can't lay that out and blanks the whole tab.
    sync_card = card(
        ft.ResponsiveRow([
            ft.Row([ft.Icon(ft.Icons.HISTORY_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                    ft.Container(sync_steps, expand=True)], spacing=12, col={"xs": 12, "lg": 6}),
            ft.Row([uid_pick, ft.FilledButton("Sync", icon=ft.Icons.SYNC_ROUNDED, on_click=guarded(do_sync)),
                    files_menu], wrap=True, spacing=12, run_spacing=8, alignment=ft.MainAxisAlignment.END,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER, col={"xs": 12, "lg": 6}),
        ], spacing=12, run_spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        link_input, sync_status, padding=ft.Padding.symmetric(horizontal=20, vertical=12))

    wishes_view = ft.Column([
        page_head(1),
        sync_card,
        stats_view,
    ], spacing=16, horizontal_alignment=STRETCH)

    # --- World tab ----------------------------------------------------------
    # Links only: both maps run in the real browser (Teyvat GPS needs its screen sharing).
    hoyolab_map_btn = ft.OutlinedButton("HoYoLAB map", icon=ft.Icons.TRAVEL_EXPLORE_ROUNDED, url=HOYOLAB_MAP_URL)
    # Teyvat GPS needs screen sharing of the PC game window, so mobile only gets the official map.
    maps_card = card(
        muted("Official interactive map: tick off chests and oculi, saved to your HoYoLAB account."),
        ft.Row([hoyolab_map_btn]),
        title="Map", icon=ft.Icons.EXPLORE_ROUNDED,
    ) if mobile else card(
        muted("Teyvat GPS follows you live by reading your minimap through screen sharing. Lock the "
              "minimap to north (Settings > Others > Mini-map Settings > Fixed), share only the game "
              "window, then teleport to a waypoint so it can find you."),
        ft.Row([ft.FilledButton("Teyvat GPS", icon=ft.Icons.MY_LOCATION_ROUNDED, url=TEYVAT_GPS_URL),
                hoyolab_map_btn], wrap=True),
        title="Live map", icon=ft.Icons.EXPLORE_ROUNDED,
    )
    world_locked = signin_prompt("Sign in to HoYoLAB to see your exploration progress.")
    world_body = ft.Column([world_locked], spacing=16, horizontal_alignment=STRETCH)
    world_view = ft.Column([page_head(2), maps_card, world_body], spacing=16, horizontal_alignment=STRETCH)
    region_cards = []  # (estimated height, card), kept so a window resize can re-flow them
    region_grid = ft.Row(spacing=16, vertical_alignment=ft.CrossAxisAlignment.START)

    def flow_regions(e=None):
        """Masonry: each card drops into the currently shortest column, so tall regions leave no gaps."""
        width = (page.width or 0) - (32 if mobile else 274)  # minus nav rail and paddings
        n = max(1, min(3, int(width // 360)))
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

    page.on_resize = flow_regions

    def region_card(w, kids):
        """One region per card: big icon + completion on top, levels as pills, sub-areas listed below."""
        pct = w["exploration_percentage"] / 10
        color = WON if pct >= 100 else GOLD
        extras = [f"Statue Lv {w['seven_statue_level']}"] if w.get("seven_statue_level") else []
        if w["type"] == "Reputation" and w["level"]:
            extras.append(f"Reputation Lv {w['level']}")
        extras += [f"{o['name']} Lv {o['level']}" for o in w.get("offerings") or []]
        icon = w.get("icon") or w.get("inner_icon")
        terrain = ft.Icon(ft.Icons.TERRAIN_ROUNDED, color=ft.Colors.ON_SURFACE_VARIANT)
        shown = bool(pct) or not kids  # a parent with 0% only groups its sub-areas
        head = ft.Row([
            # some API icon URLs 404 (Natlan, Nod-Krai) or are empty, so both fall back to a glyph
            ft.Container(ft.Image(src=icon, width=40, height=40, error_content=terrain) if icon else terrain,
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
        try:
            rec = hoyolab.game_record(vault.load(), role)
        except Exception as ex:
            world_body.controls = [card(muted(f"Could not load exploration: {ex}. Make sure Battle "
                                              "Chronicle is enabled in your HoYoLAB privacy settings."))]
            world_body.update()
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
        half = {"xs": 12, "md": 6, "lg": 3}  # 24-column row: 8 tiles fit one line on wide screens
        world_body.controls = [
            ft.ResponsiveRow(columns=24, controls=[
                tile("Days active", f"{st['active_day_number']:,}", col=half),
                tile("Achievements", f"{st['achievement_number']:,}", color=GOLD, col=half),
                tile("Characters", str(st["avatar_number"]), col=half),
                tile("Spiral Abyss", st["spiral_abyss"] or "-", color=PURPLE, col=half),
                tile("Waypoints", f"{st['way_point_number']:,}", col=half),
                tile("Domains", str(st["domain_number"]), col=half),
                tile("Chests opened", f"{chests:,}", color=GOLD, col=half),
                tile("Oculi", f"{oculi:,}", color=WON, col=half),
            ], spacing=8, run_spacing=8),
            ft.Row([ft.Icon(ft.Icons.MAP_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                    ft.Text(f"Exploration · {role['nickname']}", size=16, weight=ft.FontWeight.W_600)],
                   spacing=8),
            region_grid,
        ]
        world_body.update()

    # --- Characters tab -----------------------------------------------------
    chars_locked = signin_prompt("Sign in to HoYoLAB to see your characters and their builds.")
    chars_body = ft.Column([chars_locked], spacing=16, horizontal_alignment=STRETCH)
    characters_view = ft.Column([page_head(3), chars_body], spacing=16, horizontal_alignment=STRETCH)
    builds = {}  # character id -> (detail, property_map); fetched on first open, one call per character

    roster = {"chars": [], "role": None}  # last loaded list, re-filtered without another request
    chars_count = muted("")
    chars_grid = ft.Column(spacing=12, horizontal_alignment=STRETCH)
    META_ROLES = ("On-field DPS", "Off-field DPS", "Support")

    def char_filter(label, options, width=150):
        return ft.Dropdown(label=label, value="All", width=width, dense=True, filled=True, border_radius=14,
                           options=[ft.DropdownOption("All")] + [ft.DropdownOption(k, v) for k, v in options],
                           on_select=lambda e: show_chars())

    f_element = char_filter("Element", [(k, k) for k in ELEMENT_COLORS])
    f_weapon = char_filter("Weapon", [(v, v) for v in WEAPON_TYPES.values()])
    f_rarity = char_filter("Rarity", [("5", "5★"), ("4", "4★")], width=120)
    f_tier = char_filter("Meta tier", [(t, t) for t in PRYDWEN["tiers"]] + [("-", "Unrated")])
    f_role = char_filter("Meta role", [(r, r) for r in META_ROLES], width=170)
    f_sort = ft.Dropdown(label="Sort", value="game", width=150, dense=True, filled=True, border_radius=14,
                         options=[ft.DropdownOption("game", "HoYoLAB order"), ft.DropdownOption("tier", "Meta tier"),
                                  ft.DropdownOption("level", "Level")],
                         on_select=lambda e: show_chars())
    f_group = ft.Dropdown(label="Group by", value="none", width=150, dense=True, filled=True, border_radius=14,
                          options=[ft.DropdownOption(k, v) for k, v in (
                              ("none", "None"), ("element", "Element"), ("weapon", "Weapon"),
                              ("rarity", "Rarity"), ("tier", "Meta tier"), ("role", "Meta role"))],
                          on_select=lambda e: show_chars())
    f_search = ft.TextField(hint_text="Search characters", prefix_icon=ft.Icons.SEARCH_ROUNDED, width=220, dense=True,
                            filled=True, border_radius=14, on_change=lambda e: show_chars())
    chars_filters = ft.Row([f_search, f_element, f_weapon, f_rarity, f_tier, f_role, f_sort, f_group], wrap=True, spacing=8,
                           run_spacing=8)

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
        grid = lambda cs: ft.Row([char_tile(c, roster["role"]) for c in cs], wrap=True, spacing=10, run_spacing=10)
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
        return ft.Container(ft.Column([
            ft.Stack([portrait(c["icon"], c["rarity"], 72), *badge],
                     width=72, height=72, clip_behavior=ft.ClipBehavior.NONE),
            ft.Text(c["name"], size=14, weight=ft.FontWeight.W_600, no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS, color=ELEMENT_COLORS.get(c["element"])),
            muted(f"Lv {c['level']} · C{c['actived_constellation_num']}", size=12),
            ft.Row([ft.Image(src=w["icon"], width=20, height=20,
                             error_content=ft.Icon(ft.Icons.HARDWARE_ROUNDED, size=16)), muted(f"R{w['affix_level']}", size=12)],
                   spacing=2, tight=True),
        ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=112, padding=10, border_radius=16, bgcolor=ft.Colors.SURFACE_CONTAINER,
            tooltip=f"{c['name']} · {c['element']} · {w['name']}",
            on_click=lambda e: open_build(c, role))

    def build_view(c, d, pm):
        """Two columns on desktop (who they are | what they wear), one on mobile."""
        name = lambda p: pm.get(str(p["property_type"]), {}).get("name", "?").replace("\xa0", " ")
        section = lambda t: ft.Text(t, size=14, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY)
        color = ELEMENT_COLORS.get(c["element"], GOLD)
        splash = ft.Container(
            ft.Image(src=c.get("image") or c["icon"], height=230, fit=ft.BoxFit.CONTAIN,
                     error_content=ft.Icon(ft.Icons.PERSON_ROUNDED, size=64)),
            height=240, border_radius=STYLE["radius"], alignment=ft.Alignment.BOTTOM_CENTER,
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                       colors=[ft.Colors.with_opacity(0.45, color), ft.Colors.with_opacity(0.05, color)]))
        cons = [ft.Container(ft.Image(src=k["icon"], width=34, height=34,
                                      error_content=ft.Icon(ft.Icons.STAR_ROUNDED, size=20)),
                             width=46, height=46, border_radius=23, alignment=ft.Alignment.CENTER,
                             bgcolor=ft.Colors.with_opacity(0.35, color) if k["is_actived"]
                             else ft.Colors.SURFACE_CONTAINER_HIGHEST, opacity=1 if k["is_actived"] else 0.35,
                             tooltip=f"C{k['pos']} {k['name']}\n{clean(k['effect'])}")
                for k in sorted(d.get("constellations", []), key=lambda k: k["pos"])]
        talents = [ft.Container(ft.Column([
            ft.Image(src=t["icon"], width=34, height=34, error_content=ft.Icon(ft.Icons.BOLT_ROUNDED)),
            ft.Text(str(t["level"]), size=18, weight=ft.FontWeight.BOLD),
            muted(t["name"], size=11, text_align=ft.TextAlign.CENTER, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER), expand=True, padding=8,
            border_radius=STYLE["radius"] - 6, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            tooltip=clean(t["desc"])[:600]) for t in d["skills"] if t["skill_type"] == 1]
        stats = [ft.Container(ft.Column([
            muted(name(p), size=12),
            ft.Text(p["final"], size=16, weight=ft.FontWeight.BOLD),
            muted(f"{p['base']} + {p['add']}", size=11, visible=bool(p.get("add"))),
        ], spacing=0), padding=ft.Padding.symmetric(horizontal=10, vertical=6), border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, col={"xs": 6}) for p in d["selected_properties"]]
        w = d["weapon"]
        weapon = ft.Row([portrait(w["icon"], w["rarity"], 56, ft.Icons.HARDWARE_ROUNDED), ft.Column([
            ft.Text(w["name"], size=15, weight=ft.FontWeight.W_600),
            ft.Row([pill(f"Lv {w['level']}"), pill(f"R{w['affix_level']}", GOLD)], spacing=6),
            muted(" · ".join(f"{name(p)} {p['final']}" for p in (w["main_property"], w.get("sub_property")) if p),
                  size=12),
        ], spacing=4, expand=True)], spacing=12)
        sets = {}
        for r in d["relics"]:
            sets.setdefault(r["set"]["name"], [0, r["set"].get("affixes", [])])[0] += 1
        bonuses = [ft.Column([ft.Text(f"{n}pc {k}", size=13, weight=ft.FontWeight.W_600, color=WON)] +
                             [muted(f"{a['activation_number']}pc: {clean(a['effect'])}", size=12)
                              for a in affixes if a["activation_number"] <= n], spacing=2)
                   for k, (n, affixes) in sets.items() if n >= 2] or [muted("No set bonus.", size=12)]
        total_cv = sum(crit_value(r["sub_property_list"]) for r in d["relics"])
        relics = [ft.Container(ft.Row([portrait(r["icon"], r["rarity"], 44, ft.Icons.DIAMOND_ROUNDED), ft.Column([
            ft.Row([ft.Text(r["pos_name"], size=13, weight=ft.FontWeight.W_600, expand=True),
                    pill(f"CV {crit_value(r['sub_property_list']):.1f}", GOLD), pill(f"+{r['level']}")], spacing=4),
            ft.Text(f"{name(r['main_property'])} {r['main_property']['value']}", size=13, color=GOLD),
            muted("  ·  ".join(f"{name(p)} {p['value']}" for p in r["sub_property_list"]), size=12),
        ], spacing=2, expand=True)], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=10, border_radius=12, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH) for r in d["relics"]]
        left = ft.Column([
            splash,
            section("Constellations"), ft.Row(cons, spacing=6, wrap=True),
            section("Talents"), ft.Row(talents, spacing=8),
            section("Stats"), ft.ResponsiveRow(stats, spacing=6, run_spacing=6),
        ], spacing=10, horizontal_alignment=STRETCH, col={"xs": 12, "md": 6})
        right = ft.Column([
            section("Weapon"), weapon,
            ft.Row([section("Artifacts"), pill(f"Crit Value {total_cv:.1f}", GOLD)], spacing=8),
            *bonuses, *(relics or [muted("No artifacts equipped.")]),
        ], spacing=10, horizontal_alignment=STRETCH, col={"xs": 12, "md": 6})
        return ft.Column([ft.ResponsiveRow([left, right], spacing=20, run_spacing=16,
                                           vertical_alignment=ft.CrossAxisAlignment.START)],
                         scroll=ft.ScrollMode.AUTO, horizontal_alignment=STRETCH)

    def open_build(c, role):
        body = ft.Container(ft.ProgressRing(), width=None if mobile else 880, height=None if mobile else 600,
                            alignment=ft.Alignment.CENTER)
        page.show_dialog(ft.AlertDialog(
            inset_padding=ft.Padding.all(12) if mobile else None,
            title=ft.Row([portrait(c["icon"], c["rarity"], 44), ft.Column([
                ft.Text(c["name"], size=18, weight=ft.FontWeight.BOLD, color=ELEMENT_COLORS.get(c["element"])),
                muted(f"{c['element']} · Lv {c['level']} · C{c['actived_constellation_num']} · "
                      f"Friendship {c['fetter']}", size=13),
                ft.Row([pill(f"{t} {r}", TIER_COLORS[t]) for t, r in meta_ratings(c)]
                       or [muted("Not on Prydwen's tier list", size=12)], wrap=True, spacing=4, run_spacing=4),
            ], spacing=2, expand=True)], spacing=12),
            content=body, actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())]))

        def load():
            try:
                if c["id"] not in builds:
                    builds[c["id"]] = hoyolab.character_detail(vault.load(), role, c["id"])
                body.content, body.alignment = build_view(c, *builds[c["id"]]), None
            except Exception as ex:
                body.content = muted(f"Could not load build: {ex}")
            body.update()
        page.run_thread(load)

    def load_characters(role):
        """Character roster from Battle Chronicle (worker thread). Builds load per character on click."""
        try:
            chars = hoyolab.characters(vault.load(), role)
        except Exception as ex:
            chars_body.controls = [card(muted(f"Could not load characters: {ex}. Make sure Battle "
                                              "Chronicle is enabled in your HoYoLAB privacy settings."))]
            chars_body.update()
            return
        builds.clear()
        roster.update(chars=chars, role=role)
        chars_body.controls = [chars_filters, chars_count, chars_grid]
        show_chars()

    # --- Wiki tab -----------------------------------------------------------
    # Public catalogue (HoYoLAB wiki + paimon.moe achievements), cached in SQLite for a week.
    WIKI_CATS = {"Characters": ft.Icons.PEOPLE_ROUNDED, "Weapons": ft.Icons.HARDWARE_ROUNDED,
                 "Artifacts": ft.Icons.DIAMOND_ROUNDED, "Enemies": ft.Icons.PEST_CONTROL_ROUNDED,
                 "Achievements": ft.Icons.EMOJI_EVENTS_ROUNDED}
    WIKI_PAGE = 60  # NOTE: tiles rendered per "Show more"; switch to a virtualized GridView if it lags
    wiki_state = {"cat": "Characters", "items": [], "limit": WIKI_PAGE, "done": set()}
    wiki_search = ft.TextField(hint_text="Search", prefix_icon=ft.Icons.SEARCH_ROUNDED, width=260, dense=True,
                               filled=True, border_radius=14, on_change=lambda e: show_wiki(reset=True))
    wiki_filters = ft.Row(wrap=True, spacing=8, run_spacing=8)
    wiki_sort = ft.Dropdown(label="Sort", value="name", width=150, dense=True, filled=True, border_radius=14,
                            options=[ft.DropdownOption("name", "Name"), ft.DropdownOption("rarity", "Rarity")],
                            on_select=lambda e: show_wiki(reset=True))
    wiki_count = muted("")
    wiki_grid = ft.Column(spacing=12, horizontal_alignment=STRETCH)
    wiki_more = ft.OutlinedButton("Show more", icon=ft.Icons.EXPAND_MORE_ROUNDED, visible=False)

    def wiki_dropdown(label, values, key):
        return ft.Dropdown(label=label, value="All", width=170, dense=True, filled=True, border_radius=14, data=key,
                           options=[ft.DropdownOption("All")] + [ft.DropdownOption(v) for v in values],
                           on_select=lambda e: show_wiki(reset=True))

    def wiki_tile(e, owned):
        r = wiki.rarity(e)
        return ft.Container(ft.Column([
            ft.Stack([portrait(e["icon"], r, 72, WIKI_CATS[wiki_state["cat"]]),
                      ft.Container(ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color=WON), right=-4, top=-4,
                                   visible=owned)], width=72, height=72, clip_behavior=ft.ClipBehavior.NONE),
            ft.Text(e["name"], size=13, weight=ft.FontWeight.W_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=ft.TextAlign.CENTER),
            muted("★" * r, size=11, color=GOLD if r == 5 else PURPLE if r == 4 else None, visible=bool(r)),
        ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=104 if mobile else 120, padding=8, border_radius=STYLE["radius"] - 4, bgcolor=STYLE["card_bg"],
            border=STYLE["border"],
            tooltip=e["desc"][:400] or e["name"], url=wiki.WIKI_ENTRY_URL.format(e["id"]))

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
        picks = {d.data: d.value for d in wiki_filters.controls if d.value != "All"}
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
            owned = {c["name"] for c in roster["chars"]} if cat == "Characters" else set()
            wiki_count.value = (f"{len(shown):,} of {len(items):,} {cat.lower()}. Tap one to open it on the "
                                "HoYoLAB wiki.")
            wiki_grid.controls = [ft.Row([wiki_tile(e, e["name"] in owned) for e in shown[:wiki_state["limit"]]],
                                         wrap=True, spacing=10, run_spacing=10)]
        wiki_more.visible = len(shown) > wiki_state["limit"]
        wiki_body.update()

    def more_wiki(e):
        wiki_state["limit"] += WIKI_PAGE
        show_wiki()

    wiki_more.on_click = more_wiki

    def load_wiki(refresh=False):
        """Fetch (or read the cache of) the picked category, then rebuild its filter bar. Worker thread."""
        cat = wiki_state["cat"]
        wiki_count.value, wiki_grid.controls = f"Loading {cat.lower()}...", [ft.ProgressRing()]
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
                wiki_dropdown("Category", sorted({a["category"] for a in items}), "category"),
                wiki_dropdown("Status", ["Done", "To do"], "status")]
        else:
            wiki_filters.controls = [wiki_dropdown(wiki.label(k), vs, k) for k, vs in wiki.filters(items).items()]
        wiki_sort.visible = cat not in ("Achievements", "Enemies")
        show_wiki(reset=True)
        if refresh:
            return f"{cat} updated."

    def pick_wiki_cat(e):
        wiki_state["cat"] = e.control.selected[0]
        wiki_search.value = ""
        page.run_thread(load_wiki)

    wiki_cat = ft.SegmentedButton(selected=["Characters"], show_selected_icon=False, on_change=pick_wiki_cat,
                                  segments=[ft.Segment(k, label=k, icon=i) for k, i in WIKI_CATS.items()])
    wiki_body = ft.Column([
        ft.Row([wiki_cat], scroll=ft.ScrollMode.AUTO),
        ft.Row([wiki_search, wiki_sort, ft.IconButton(ft.Icons.REFRESH_ROUNDED, tooltip="Download again",
                                                      on_click=guarded(lambda: load_wiki(refresh=True)))],
               wrap=True, spacing=8, run_spacing=8),
        wiki_filters, wiki_count, wiki_grid, ft.Row([wiki_more]),
    ], spacing=12, horizontal_alignment=STRETCH)
    wiki_view = ft.Column([page_head(WIKI), wiki_body], spacing=16, horizontal_alignment=STRETCH)

    # --- Account tab --------------------------------------------------------
    account_icon = ft.Icon(ft.Icons.NO_ACCOUNTS_ROUNDED, size=28)
    account_title = ft.Text(size=18, weight=ft.FontWeight.W_600)
    account_sub = muted("")
    logout_btn = ft.OutlinedButton("Sign out", icon=ft.Icons.LOGOUT_ROUNDED)
    status_dot = ft.Container(width=8, height=8, border_radius=4)
    status_label = ft.Text(size=13, weight=ft.FontWeight.W_500)
    cookie_field = ft.TextField(label="HoYoLAB cookies", password=True, can_reveal_password=True,
                                border_radius=14, filled=True)
    profiles = ft.Column(spacing=16, horizontal_alignment=STRETCH)

    def role_card(r):
        count = db.count_wishes(db.connect(), r["game_uid"])
        return hero(ft.Row([
            ft.Container(ft.Text(r["nickname"][:1].upper(), size=24, weight=ft.FontWeight.BOLD,
                                 color="#1B1608"),
                         width=56, height=56, border_radius=28, alignment=ft.Alignment.CENTER,
                         gradient=ft.LinearGradient(colors=[GOLD, "#C9965A"])),
            ft.Column([
                ft.Text(r["nickname"], size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                muted(f"{r['region_name']} · UID {r['game_uid']}"),
                muted(f"{count:,} wishes logged" if count else "No wishes logged yet", size=13),
            ], spacing=2, expand=True),
            ft.Column([ft.Text(str(r["level"]), size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                       muted("AR", size=12)], spacing=0,
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=16))

    def load_profiles():
        """Fetch the Genshin accounts bound to this HoYoLAB login (runs on a worker thread)."""
        roles = []
        if not logged_in():
            profiles.controls = []
        else:
            try:
                roles = hoyolab.game_roles(vault.load())
                bound_roles[:] = roles
                profiles.controls = [role_card(r) for r in roles] or [
                    card(muted("No Genshin account bound to this HoYoLAB login."))]
            except Exception as ex:
                profiles.controls = [card(muted(f"Could not load game accounts: {ex}"))]
        account_pick.options = [ft.DropdownOption(r["game_uid"], f"{r['nickname']} · UID {r['game_uid']}")
                                for r in roles]
        account_pick.value = active_role()["game_uid"] if roles else None
        account_row.visible = len(roles) > 1  # a picker with one choice is just noise
        page.update()
        ensure_loaded(current["i"])

    def signed_in(cookies):
        vault.save(cookies)
        cookie_field.value = ""
        show_auth()
        page.update()
        page.run_thread(load_rewards)
        page.run_thread(load_profiles)
        if "cookie_token_v2" not in cookies:
            return "Signed in. No cookie_token_v2, so redeeming codes will not work."
        return "Signed in."

    def do_signin():
        toast("Log in on the HoYoLAB window. It closes by itself when you are done.")
        return signed_in(weblogin.sign_in())

    def do_cookie_login():
        cookies = vault.parse_cookie_string(cookie_field.value or "")
        missing = [k for k in ("ltoken_v2", "ltuid_v2") if k not in cookies]
        if missing:
            return f"Missing {', '.join(missing)}."
        return signed_in(cookies)

    def do_logout(e):
        page.pop_dialog()
        vault.delete()
        bound_roles.clear()
        loaded.difference_update({WORLD, CHARACTERS})
        account_row.visible = False
        profiles.controls = []
        world_body.controls = [world_locked]
        chars_body.controls = [chars_locked]
        show_auth()
        page.update()
        toast("Signed out.")

    def confirm_logout(e):
        # Signing back in means fetching cookies again, so ask before throwing them away.
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Sign out of HoYoLAB?"),
            content=muted("Your wish history stays on this device. You'll need to sign in again to "
                          "check in, redeem codes and see exploration."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                     ft.FilledButton("Sign out", on_click=do_logout)]))

    logout_btn.on_click = confirm_logout

    signin_card = card(
        muted("Opens the official hoyolab.com login. Teyvault never sees your password."),
        ft.Row([ft.FilledButton("Sign in with HoYoLAB", icon=ft.Icons.LOGIN_ROUNDED, on_click=guarded(do_signin))]),
        title="Sign in", icon=ft.Icons.KEY_ROUNDED)
    cookie_card = card(ft.ExpansionTile(
        # Without the login window (mobile) cookies are the only way in, so start expanded there.
        title=ft.Text("Sign in with browser cookies" if not has_webview else "Use browser cookies instead"),
        expanded=not has_webview, tile_padding=0,
        controls_padding=ft.Padding.only(bottom=8), shape=ft.RoundedRectangleBorder(),
        collapsed_shape=ft.RoundedRectangleBorder(),
        expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
        controls=[ft.Column([
            muted(COOKIE_HELP),
            ft.Text("These cookies give full access to your HoYoLAB account. Never share them.",
                    color=ft.Colors.ERROR, size=13),
            cookie_field,
            ft.FilledTonalButton("Save cookies", icon=ft.Icons.SAVE_ROUNDED,
                                 on_click=guarded(do_cookie_login)),
        ], spacing=12)],
    ))

    def show_auth():
        """Show only what makes sense for the current login state, on every tab."""
        on = logged_in()
        account_icon.icon = ft.Icons.VERIFIED_USER_ROUNDED if on else ft.Icons.NO_ACCOUNTS_ROUNDED
        account_icon.color = WON if on else ft.Colors.ON_SURFACE_VARIANT
        account_title.value = "Signed in to HoYoLAB" if on else "Not signed in"
        account_sub.value = ("Credentials stay on this device." if on
                             else "Sign in to check in, redeem codes and see exploration.")
        logout_btn.visible = on
        signin_card.visible = not on and has_webview
        cookie_card.visible = not on
        status_dot.bgcolor = WON if on else LOST
        status_label.value = "Signed in" if on else "Signed out"
        checkin_hero.visible = redeem_card.visible = on
        today_locked.visible = not on
        if not on:
            rewards_card.visible = False

    account_view = ft.Column([
        page_head(ACCOUNT),
        card(ft.Row([account_icon, ft.Column([account_title, account_sub], spacing=2, expand=True),
                     logout_btn], spacing=16)),
        profiles,
        signin_card,
        cookie_card,
    ], spacing=16, horizontal_alignment=STRETCH)

    # --- Settings tab -------------------------------------------------------
    def set_auto_checkin(e):
        db.set_meta(db.connect(), "auto_checkin", "1" if e.control.value else "0")
        show_auto_note()
        page.update()

    def set_pref(key):
        def handler(e):
            db.set_meta(db.connect(), key, e.control.value)
            seed_pick.visible = style_pick.value == "material"
            page.update()
            toast("Restart Teyvault to apply the theme.")
        return handler

    style_pick = ft.Dropdown(label="Style", value=style, width=220, dense=True, filled=True, border_radius=14,
                             options=[ft.DropdownOption(k, v) for k, v in STYLES.items()], on_select=set_pref("style"))
    seed_pick = ft.Dropdown(label="Material You color", value=seed, width=220, dense=True, filled=True,
                            border_radius=14, visible=style == "material", on_select=set_pref("seed"),
                            options=[ft.DropdownOption(k, v, leading_icon=ft.Icon(ft.Icons.CIRCLE_ROUNDED, color=k))
                                     for k, v in SEEDS.items()])

    def set_account(e):
        db.set_meta(db.connect(), "default_uid", e.control.value)
        uid_pick.value = None  # let the Wishes tab follow the new default
        refresh_stats()
        loaded.difference_update({WORLD, CHARACTERS})
        ensure_loaded(current["i"])

    account_pick = ft.Dropdown(label="Game account", width=320, dense=True, filled=True, border_radius=14,
                               on_select=set_account)
    account_row = ft.Column([muted("Which account World, Characters and Wishes show first."), account_pick],
                            spacing=8, visible=False)
    prefs_card = card(
        ft.Switch(label="Check in automatically when Teyvault opens", value=auto_on(), on_change=set_auto_checkin),
        ft.Row([ft.Dropdown(label="Mode", value=theme, width=220, dense=True, filled=True, border_radius=14,
                            options=[ft.DropdownOption(k, v) for k, v in THEMES.items()], on_select=set_pref("theme")),
                style_pick, seed_pick], wrap=True, spacing=12, run_spacing=12),
        muted("Classic: Teyvault's own look. Material You: Google's tonal colors. Glass: frosted, translucent "
              "cards. Nothing: black, white and one red.", size=12),
        account_row,
        title="Preferences", icon=ft.Icons.TUNE_ROUNDED)

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
        refresh_stats()
        return f"Received {added} new wishes."

    phone_card = card(
        muted("On Teyvault for PC, open Settings > Phone sync and press Start sharing, then enter the address "
              "and PIN it shows. Both devices must be on the same Wi-Fi. Only wish history is sent, never "
              "your sign-in."),
        pc_addr, ft.Row([pc_pin, ft.FilledButton("Receive", icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=guarded(do_receive))],
                        spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
        title="Receive from PC", icon=ft.Icons.PHONELINK_ROUNDED) if mobile else card(
        muted("Send your wish history to Teyvault on your phone. Both devices must be on the same Wi-Fi. "
              "On the phone, open Settings > Receive from PC and enter the address and PIN below. Only "
              "wish history is sent, never your sign-in. Sharing stops after 5 wrong PINs."),
        share_info, ft.Row([share_btn]),
        title="Phone sync", icon=ft.Icons.PHONELINK_ROUNDED)

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
        refresh_stats()
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
                ft.OutlinedButton("Export a backup first", icon=ft.Icons.SAVE_ALT_ROUNDED, on_click=do_export),
                del_ok,
            ], tight=True, spacing=12),
            actions=[ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()), del_btn]))

    data_card = card(
        muted("Wish history is stored in:"),
        ft.Text(str(db.default_path()), selectable=True, size=13, font_family="monospace"),
        ft.Row([ft.FilledTonalButton("Import file", icon=ft.Icons.FILE_OPEN_ROUNDED, on_click=do_import,
                                     tooltip="UIGF JSON or Excel from another wish tracker"),
                ft.OutlinedButton("Export UIGF", icon=ft.Icons.SAVE_ALT_ROUNDED, on_click=do_export),
                ft.OutlinedButton("Export Excel", icon=ft.Icons.TABLE_VIEW_ROUNDED, on_click=do_export_xlsx)],
               wrap=True, spacing=8, run_spacing=8),
        ft.Row([ft.OutlinedButton("Delete wish history", icon=ft.Icons.DELETE_OUTLINE_ROUNDED, on_click=confirm_delete,
                                  style=ft.ButtonStyle(color=ft.Colors.ERROR))]),
        title="Your data", icon=ft.Icons.STORAGE_ROUNDED)

    try:
        version = importlib.metadata.version("teyvault")
    except importlib.metadata.PackageNotFoundError:  # running from a flet build
        version = ""
    about_card = card(
        ft.Row([logo_badge(), ft.Column([ft.Text(f"{APP} {version}".strip(), size=16, weight=ft.FontWeight.W_600),
                                         muted(f"Made by {APP_AUTHOR}. Free and open source.", size=13)],
                                        spacing=2, expand=True)], spacing=12),
        ft.Row([ft.OutlinedButton("Source code on GitHub", icon=ft.Icons.CODE_ROUNDED, url=APP_REPO)]),
        muted("Not affiliated with HoYoverse. Genshin Impact content and images belong to HoYoverse.", size=12),
        title="About", icon=ft.Icons.INFO_OUTLINE_ROUNDED)

    settings_view = ft.Column([page_head(SETTINGS), prefs_card, phone_card, data_card, about_card], spacing=16,
                              horizontal_alignment=STRETCH)

    # --- Shell --------------------------------------------------------------
    # PC: sidebar (lots of width, mouse). Mobile: bottom bar (thumb reach) + app bar with the page title.
    # All tabs stay mounted (only visibility toggles) so background updates never hit a detached control.
    views = [today_view, wishes_view, world_view, characters_view, wiki_view, account_view, settings_view]
    section_title = ft.Text(SECTIONS[0][0], size=20, weight=ft.FontWeight.BOLD)

    def select(i):
        current["i"] = i
        ensure_loaded(i)
        if i < len(nav.destinations):  # mobile's bottom bar has no Settings; it keeps the last tab lit
            nav.selected_index = i
        section_title.value = SECTIONS[i][0]
        for j, v in enumerate(views):
            v.visible = j == i
        page.update()

    status_chip = ft.Container(
        ft.Row([status_dot, status_label], spacing=6, tight=True),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6), border_radius=20,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, on_click=lambda e: select(ACCOUNT),
        tooltip="Account",
    )
    logo = logo_badge()
    watermark = ft.Container(
        ft.Row([ft.Icon(ft.Icons.CODE_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                muted(f"Made by {APP_AUTHOR}", size=12)], spacing=6, tight=True),
        url=APP_REPO, tooltip=APP_REPO, padding=ft.Padding.symmetric(horizontal=8, vertical=4), border_radius=8)
    on_change = lambda e: select(e.control.selected_index)

    if mobile:
        nav = ft.NavigationBar(on_change=on_change, destinations=[
            ft.NavigationBarDestination(icon=icon, selected_icon=sel, label=label)
            for label, icon, sel, _ in SECTIONS[:ACCOUNT]])
        page.navigation_bar = nav
        page.appbar = ft.AppBar(title=section_title, bgcolor=ft.Colors.SURFACE, center_title=False,
                                actions=[ft.IconButton(ft.Icons.SETTINGS_OUTLINED, tooltip="Settings",
                                                       on_click=lambda e: select(SETTINGS)),
                                         ft.Container(status_chip, padding=ft.Padding.only(right=12))])
        body = ft.SafeArea(ft.Column(views, scroll=ft.ScrollMode.AUTO, spacing=16,
                                     horizontal_alignment=STRETCH), expand=True, minimum_padding=16)
    else:
        nav = ft.NavigationRail(
            on_change=on_change, selected_index=0, extended=True, min_extended_width=210,
            group_alignment=-0.85, bgcolor=ft.Colors.SURFACE_CONTAINER,
            leading=ft.Container(ft.Row([logo, ft.Column([
                ft.Text(APP, size=20, weight=ft.FontWeight.BOLD),
                muted(datetime.date.today().strftime("%a, %d %b"), size=13)], spacing=0)], spacing=12),
                padding=ft.Padding.only(top=12, bottom=24)),
            trailing=ft.Container(ft.Column([status_chip, watermark], spacing=8,
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                  padding=ft.Padding.only(bottom=16)),
            pin_trailing_to_bottom=True,
            destinations=[ft.NavigationRailDestination(icon=icon, selected_icon=sel, label=label)
                          for label, icon, sel, _ in SECTIONS])
        content = ft.Column(views, scroll=ft.ScrollMode.AUTO, spacing=16, horizontal_alignment=STRETCH)
        if STYLE["page_bg"]:
            nav.bgcolor = STYLE["card_bg"]
        body = ft.Row([nav, ft.Container(content, expand=True, padding=ft.Padding.only(top=8, right=32, bottom=16))],
                      spacing=32, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        if desktop:
            body = ft.Column([title_bar_for(page), body], spacing=0, expand=True)

    if STYLE["page_bg"]:  # Glass: everything floats over one gradient
        page.bgcolor = STYLE["page_bg"][1]
        body = ft.Container(body, expand=True, gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=STYLE["page_bg"]))
    for i, v in enumerate(views):
        v.visible = i == 0
    show_auth()
    page.add(body)
    refresh_stats()

    last = db.get_meta(db.connect(), "last_checkin")
    show_checkin(last)
    show_auto_note()
    page.update()

    def auto_checkin():
        if last == today() or not logged_in() or not auto_on():
            return
        try:
            toast(f"Daily check-in: {do_checkin()}")
        except Exception as ex:
            toast(f"Daily check-in failed: {ex}")

    def startup():
        # One request at a time, like a person using the website, never a burst.
        auto_checkin()
        load_rewards()
        load_profiles()
        # Character/weapon catalogue (cached a week) gives wish portraits for releases paimon.moe lacks.
        try:
            for cat in ("Characters", "Weapons"):
                wiki.entries(db.connect(), cat)
            refresh_stats()
        except Exception:
            pass  # offline: paimon.moe icons and initials still work

    page.run_thread(startup)


def run():
    ft.run(main)


if __name__ == "__main__":
    run()
