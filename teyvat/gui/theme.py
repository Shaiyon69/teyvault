"""Colors, theme styles and branding, shared by every GUI file."""
import os
import re
from pathlib import Path

import flet as ft

from teyvat import wish

APP = "Teyvault"
GOLD, PURPLE, WON, LOST = "#E6C07B", "#B58CF5", "#7BD4A8", "#F08A8A"
ELEMENT_COLORS = {"Pyro": "#F08A5D", "Hydro": "#5DB4F0", "Anemo": "#74D9C0", "Electro": "#B58CF5",
                  "Dendro": "#A5D65B", "Cryo": "#9FDDF0", "Geo": "#E6C07B"}
RARITY_BG = {5: ["#9C6B3A", "#C9965A"], 4: ["#5E4A8C", "#8A6CC0"], 3: ["#3E6A8C", "#5A93B5"],
             2: ["#3E7A5E", "#5AA07E"], 1: ["#5A5F70", "#7A8090"]}
PRYDWEN = wish.load_data("prydwen_tiers.json")
TIER_COLORS = {}  # filled by use_palette
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
STYLES = {"clean": "Clean", "classic": "Classic", "material": "Material You", "glass": "Glass", "nothing": "Nothing"}
# Clean (the default): flat grey layers, each a step lighter than the one under it, no borders or gradients,
# so the accents are the only color on screen. (window, panel, card, raised, highest, muted, text)
CLEAN = {False: ("#0D1117", "#161B22", "#21262D", "#30363D", "#3D444D", "#8B949E", "#FFFFFF"),
         True: ("#FFFFFF", "#F6F8FA", "#EAEEF2", "#D0D7DE", "#C4CBD3", "#57606A", "#1F2328")}


def gtk_colors(path=Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "gtk-4.0" / "gtk.css"):
    """`@define-color` values from the GTK4 user CSS (and the files it @imports), which shells like Noctalia,
    matugen or DankMaterialShell regenerate from the wallpaper. {} when there is none."""
    colors, seen = {}, set()

    def read(f):
        if f in seen or not f.is_file():
            return
        seen.add(f)
        text = f.read_text(errors="ignore")
        for name in re.findall(r'@import\s+url\(["\']?([^"\')]+)', text):
            read(f.parent / name)
        colors.update(re.findall(r"@define-color\s+(\w+)\s+([^;]+);", text))

    read(path)
    for _ in range(3):  # resolve "@window_bg_color" style references
        colors = {k: colors.get(v[1:], v) if v.startswith("@") else v for k, v in colors.items()}
    return {k: v.strip() for k, v in colors.items() if re.fullmatch(r"#[0-9a-fA-F]{6}", v.strip())}


def _mix(a, b, t):
    """Hex color t of the way from a to b."""
    x, y = (int(a[i:i + 2], 16) for i in (1, 3, 5)), (int(b[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(p + (q - p) * t):02X}" for p, q in zip(x, y))


def _niri():
    """Niri style: the Clean layers rebuilt from the desktop's GTK colors, so the app follows the system theme.
    (layers like CLEAN, accent, on-accent, is-light) or None off Linux / without GTK colors."""
    c = gtk_colors() if os.name == "posix" else {}
    bg, text, accent = c.get("window_bg_color"), c.get("window_fg_color"), c.get("accent_color")
    if not (bg and text and accent):
        return None
    card = c.get("card_bg_color", _mix(bg, text, 0.08))
    light = sum(int(bg[i:i + 2], 16) for i in (1, 3, 5)) > 3 * 128
    return ((bg, _mix(bg, card, 0.5), card, _mix(card, text, 0.1), _mix(card, text, 0.16), _mix(text, bg, 0.4),
             text), accent, c.get("accent_fg_color", bg), light)


# NOTE: read once at import; a wallpaper/theme change shows after the next restart (Settings style pick or relaunch).
NIRI = _niri()
if NIRI:
    STYLES["niri"] = "Niri (system colors)"
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
# How cards/heroes look per style; set by use_style() before the controls are built.
STYLE = {"name": "classic", "radius": 20, "card_bg": ft.Colors.SURFACE_CONTAINER, "border": None, "blur": None,
         "hero": ["#3A2F5C", "#1F2340"], "page_bg": None, "heading_font": None, "bg": None, "panel": None}
CLASSIC = dict(STYLE)
NIGHT_ACCENTS, NIGHT_ELEMENTS = (GOLD, PURPLE, WON, LOST), dict(ELEMENT_COLORS)


def use_palette(light):
    """Accent colors for the theme mode. Run before the controls are built: they copy the values, so a theme
    change rebuilds the UI (gui.main's restart)."""
    global GOLD, PURPLE, WON, LOST
    GOLD, PURPLE, WON, LOST = DAY_ACCENTS if light else NIGHT_ACCENTS
    ELEMENT_COLORS.update(DAY_ELEMENTS if light else NIGHT_ELEMENTS)
    TIER_COLORS.update(zip(PRYDWEN["tiers"], [LOST, "#B8641C", GOLD, "#8E8A12", WON, "#1F7AC0", PURPLE, "#5E6380"] if light
                           else [LOST, "#F0A86A", GOLD, "#D9D46A", WON, "#5DB4F0", PURPLE, "#8A8FA8"]))


use_palette(False)


def use_style(name, light, mobile):
    """Card/hero look for a theme style. Same rebuild-to-apply rule as use_palette."""
    STYLE.clear()
    STYLE.update(CLASSIC)
    glass_tint = ft.Colors.with_opacity(0.55 if light else 0.07, ft.Colors.WHITE)
    if name == "niri" and not NIRI:
        name = "clean"
    bg, panel, card_bg = (NIRI[0] if name == "niri" else CLEAN[light])[:3]
    STYLE.update({
        "clean": {"name": name, "radius": 14, "card_bg": card_bg, "hero": None, "bg": bg, "panel": panel},
        "material": {"name": name, "radius": 28, "card_bg": ft.Colors.SURFACE_CONTAINER_HIGH, "hero": None},
        "glass": {"name": name, "radius": 22, "card_bg": glass_tint,
                  "border": ft.Border.all(1, ft.Colors.with_opacity(0.6 if light else 0.14, ft.Colors.WHITE)),
                  "blur": None if mobile else ft.Blur(18, 18),  # backdrop blur is costly on phones
                  "page_bg": ["#E9E2FF", "#F7F5FB", "#DDF2FF"] if light else ["#2A1B5C", "#0E1020", "#0B3346"]},
        "nothing": {"name": name, "radius": 12, "card_bg": ft.Colors.SURFACE,
                    "border": ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), "hero": None, "heading_font": "Doto"},
    }.get("clean" if name == "niri" else name, {}))  # Niri = Clean's layout in the system colors


# Slim, trackless scrollbar that only shows while scrolling or hovered, tinted with the theme's accent.
# PC pages scroll inside a right gutter (gui.main's GUTTER), so the thumb never sits on top of a card.
SCROLLBAR = ft.ScrollbarTheme(
    thickness={ft.ControlState.HOVERED: 6, ft.ControlState.DEFAULT: 3}, radius=3, interactive=True,
    thumb_visibility=False, track_visibility=False, track_color=ft.Colors.TRANSPARENT,
    track_border_color=ft.Colors.TRANSPARENT, cross_axis_margin=1, main_axis_margin=6, min_thumb_length=40,
    thumb_color={ft.ControlState.HOVERED: ft.Colors.with_opacity(0.7, ft.Colors.PRIMARY),
                 ft.ControlState.DRAGGED: ft.Colors.PRIMARY,
                 ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.35, ft.Colors.ON_SURFACE_VARIANT)})


def make_theme(style, light, seed):
    if style == "material":
        return ft.Theme(color_scheme_seed=seed, use_material3=True, font_family="Inter", scrollbar_theme=SCROLLBAR)
    if style == "niri" and NIRI:
        layers, accent, on_accent, _ = NIRI
    if style == "clean" or style == "niri" and NIRI:
        bg, panel, _, raised, highest, muted_, text = layers if style == "niri" else CLEAN[light]
        scheme = ft.ColorScheme(
            primary=accent if style == "niri" else DAY_ACCENTS[0] if light else "#E6C07B",
            on_primary=on_accent if style == "niri" else "#FFFFFF" if light else "#1B1608",
            secondary=DAY_ACCENTS[1] if light else "#B58CF5", surface=panel, on_surface=text,
            on_surface_variant=muted_, surface_container=bg, surface_container_high=raised,
            surface_container_highest=highest, outline_variant=raised)
    else:
        scheme = (NOTHING_LIGHT if light else NOTHING_DARK) if style == "nothing" else DAY if light else NIGHT
    return ft.Theme(color_scheme=scheme, font_family="Inter", scrollbar_theme=SCROLLBAR)



def accents():
    """GOLD, PURPLE, WON, LOST as they are now. Call it when building controls: use_palette() rebinds
    them, so a name imported from this module at import time would keep the dark-theme value."""
    return GOLD, PURPLE, WON, LOST
