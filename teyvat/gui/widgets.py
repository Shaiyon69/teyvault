"""Small control builders with no state of their own: cards, tiles, calendars, portraits."""
import calendar
import datetime
import re

import flet as ft

from teyvat import db, wiki, wish
from teyvat.gui import theme
from teyvat.gui.theme import APP, NIGHT, PRYDWEN, RARITY_BG, SCROLLBAR, STRETCH, STYLE

def today() -> str:
    return datetime.date.today().isoformat()


def label(text, **kw):
    """Card/stat label: small UPPERCASE text, the one heading style inside cards."""
    return ft.Text(text.upper(), **{"size": 12, "weight": ft.FontWeight.W_500, "color": ft.Colors.ON_SURFACE, **kw})


def card(*controls, title=None, **kw):
    head = [label(title)] if title else []
    return ft.Container(ft.Column(head + list(controls), spacing=12, horizontal_alignment=STRETCH),
                        **{"padding": 21, "border_radius": STYLE["radius"], "bgcolor": STYLE["card_bg"],
                           "border": STYLE["border"], "blur": STYLE["blur"], **kw})


def hero(content, **kw):
    """Highlight card. Classic/Glass: purple gradient, always dark-themed so its text stays readable in
    light mode too. Material You / Nothing: the style's own accent surface."""
    if STYLE["hero"] is None:
        accent = ft.Colors.PRIMARY_CONTAINER if STYLE["name"] == "material" else STYLE["card_bg"]
        return ft.Container(content, padding=24, border_radius=STYLE["radius"] + 4, bgcolor=accent,
                            border=ft.Border.all(1, ft.Colors.PRIMARY) if STYLE["name"] == "nothing" else None, **kw)
    return ft.Container(content, padding=24, border_radius=STYLE["radius"] + 4, theme=ft.Theme(color_scheme=NIGHT, font_family="Inter",
                                                                                           scrollbar_theme=SCROLLBAR),
                        theme_mode=ft.ThemeMode.DARK, border=STYLE["border"], blur=STYLE["blur"],
                        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                                   colors=STYLE["hero"]), **kw)


def muted(text, **kw):
    return ft.Text(text, **{"size": 14, "color": ft.Colors.ON_SURFACE_VARIANT, **kw})


def pity_color(pity, hard):
    """Green = early (lucky), gold = before soft pity, red = soft/hard pity."""
    ratio = pity / hard
    return theme.WON if ratio < 0.5 else theme.GOLD if ratio < 0.82 else theme.LOST


def bar(value, color, height=6):
    return ft.ProgressBar(value=value, color=color, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                          bar_height=height, border_radius=height / 2, expand=True)


def pity_meter(label, pity, hard, color):
    return ft.Column([
        ft.Row([muted(label, expand=True), ft.Text(str(pity), size=16, weight=ft.FontWeight.BOLD,
                                                   color=color), muted(f"/ {hard}")], spacing=4),
        ft.Row([bar(pity / hard, color)]),
    ], spacing=6)


def tile(name, value, sub="", color=None, raised=True, **kw):
    """Label + one big number. raised: a tile inside a card; otherwise a stat card of its own."""
    return ft.Container(ft.Column([
        label(name) if not raised else muted(name, size=13),
        ft.Text(value, size=20 if raised else 26, weight=ft.FontWeight.W_600, color=color),
        muted(sub, size=12, visible=bool(sub)),
    ], spacing=2 if raised else 6), padding=12 if raised else 21,
        border_radius=STYLE["radius"] - 6 if raised else STYLE["radius"],
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH if raised else STYLE["card_bg"],
        border=None if raised else STYLE["border"], **kw)


def item_icon(name, item_type, size=36, rarity=5):
    """Character/weapon portrait on its rarity backdrop. HoYoLAB's wiki icon first (it has new releases
    on day one), then paimon.moe's, then the initial."""
    initial = ft.Text(name[:1], size=size / 2.4, weight=ft.FontWeight.BOLD)
    paimon = ft.Image(src=wiki.image(wish.icon_url(name, item_type)), width=size, height=size, error_content=initial)
    src = wiki.icon_for(name)
    return ft.Container(
        ft.Image(src=wiki.image(src), width=size, height=size, error_content=paimon) if src else paimon,
        width=size, height=size, border_radius=size / 2, alignment=ft.Alignment.CENTER,
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                   colors=RARITY_BG[rarity]),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS, tooltip=name,
    )


def clean(text) -> str:
    """HoYoLAB rich text -> plain: drop <color> tags and {LINK#...} markers."""
    return re.sub(r"<[^>]+>|\{/?LINK[^}]*\}", "", text or "").replace(r"\n", "\n")


def reward_tile(day, award, claimed, current, icon=36, height=None):
    """One day of the monthly check-in calendar, using HoYoLAB's own reward icon."""
    return ft.Container(ft.Column([
        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color=theme.WON) if claimed else muted(f"Day {day}", size=11, no_wrap=True),
        ft.Image(src=wiki.image(award["icon"]), width=icon, height=icon,
                 error_content=ft.Icon(ft.Icons.CARD_GIFTCARD_ROUNDED, color=ft.Colors.ON_SURFACE_VARIANT)),
        ft.Text(f"×{award['cnt']:,}", size=12, weight=ft.FontWeight.W_600),
    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
        col=1, padding=4, border_radius=12, height=height, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        opacity=0.45 if claimed and not current else 1,
        border=ft.Border.all(2, theme.WON if claimed else theme.GOLD) if current else None,
        tooltip=f"Day {day}: {award['name']} ×{award['cnt']:,}" + (" (claimed)" if claimed else ""))


def event_art(e):
    """paimon.moe's banner art for an event, its CSS background-position ("50% 20%") as the alignment."""
    art = wiki.event_image(e)
    px, py = (float(v[:-1]) / 50 - 1 if v.endswith("%") else 0 for v in (e.get("pos") or "50% 50%").split()[:2])
    return art and ft.DecorationImage(src=wiki.image(art), fit=ft.BoxFit.COVER, alignment=ft.Alignment(px, py))


def month_calendar(month, events, selected, on_pick, compact=False):
    """Month grid (weeks start Monday). A day an event starts or ends shows that event's art as background
    (starts win when both fall on one day). Names are in the tooltip and the details card. Tapping a day calls
    on_pick(date). Compact (phones): fixed 64 px cells; otherwise the weeks share the height it is given."""
    now = datetime.datetime.now().astimezone()
    local = lambda dt: dt.astimezone().date()
    last = lambda x: local(x[2] - datetime.timedelta(seconds=1))
    weeks = calendar.Calendar().monthdatescalendar(month.year, month.month)

    def day_cell(d):
        on = [x for x in events if local(x[1]) <= d <= last(x)]
        is_today = d == now.date()
        edge = sorted((x for x in on if d in (local(x[1]), last(x))), key=lambda x: local(x[1]) != d)
        art = next((a for a in map(event_art, (x[0] for x in edge)) if a), None)
        return ft.Container(ft.Column([
            ft.Row([ft.Container(ft.Text(str(d.day), size=12, weight=ft.FontWeight.W_600,
                                         color=ft.Colors.ON_PRIMARY if is_today else
                                         ft.Colors.WHITE if art else None),
                                 width=22, height=22, alignment=ft.Alignment.CENTER, border_radius=11,
                                 bgcolor=ft.Colors.PRIMARY if is_today else
                                 ft.Colors.with_opacity(0.6, ft.Colors.BLACK) if art else None)],
                   alignment=ft.MainAxisAlignment.CENTER),
        ], horizontal_alignment=STRETCH),
            expand=1, height=64 if compact else None, padding=ft.Padding.symmetric(vertical=4), border_radius=10,
            opacity=1 if d.month == month.month else 0.35,
            image=art, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border=ft.Border.all(1, ft.Colors.PRIMARY) if d == selected else None,
            on_click=lambda _, d=d: on_pick(d),
            tooltip=None if compact else "\n".join(e["name"] for e, *_ in on) or None)

    head = ft.Row([ft.Container(muted(n[:1] if compact else n, size=11), expand=1, alignment=ft.Alignment.CENTER)
                   for n in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")], spacing=0)
    # compact sits in the page scroll (unbounded height): STRETCH there asks for an infinite cell and draws nothing
    return ft.Column([head] + [ft.Row([day_cell(d) for d in w], spacing=4, expand=not compact,
                                      vertical_alignment=None if compact else STRETCH) for w in weeks],
                     spacing=4, expand=not compact)


def timeline_chart(rows, on_pick, day_px=28, row_h=40, height=None):
    """Gantt of event rows [(event, start, end), ...], from a week ago to the last end (at most two months ahead).
    Pans sideways by drag (mouse too); tapping a bar calls on_pick(event, start, end).
    `height`: squeeze the rows to fit it (no vertical scroll); names hide once bars get too thin to hold them."""
    now = datetime.datetime.now().astimezone()
    first = datetime.datetime.combine(now.date() - datetime.timedelta(7), datetime.time(), now.tzinfo)
    rows = [r for r in ([x for x in row if x[2] > first] for row in rows) if r]
    if height:  # minus the date header (36 + 8 spacing)
        row_h = max(8, min(row_h, (height - 44) / max(len(rows), 1)))
    gap, font = min(6, row_h * 0.15), min(12, row_h * 0.45)
    days = min(max([(x[2] - first).days + 1 for r in rows for x in r], default=21), 63)
    width = days * day_px
    pos = lambda dt: min(max((dt - first).total_seconds() / 86400 * day_px, 0), width)

    header = ft.Row(spacing=0, controls=[
        ft.Container(ft.Text(f"{d:%b}" if d.day == 1 or i == 0 else f"{d:%a}"[:2], text_align=ft.TextAlign.CENTER,
                             spans=[ft.TextSpan(f"\n{d.day}", ft.TextStyle(weight=ft.FontWeight.BOLD))], size=11,
                             color=ft.Colors.ON_PRIMARY if d == now.date() else ft.Colors.ON_SURFACE_VARIANT),
                     width=day_px, height=36, alignment=ft.Alignment.CENTER, border_radius=8,
                     bgcolor=ft.Colors.PRIMARY if d == now.date() else None)
        for i, d in enumerate(first.date() + datetime.timedelta(n) for n in range(days))])
    bars = []
    for y, row in enumerate(rows):
        for e, start, end in row:
            x0 = pos(start)
            color = e.get("color", theme.GOLD)
            bars.append(ft.Container(
                ft.Container(ft.Text(e["name"], size=font, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE,
                                     visible=row_h >= 16,
                                     no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS,
                                     style=ft.TextStyle(shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.BLACK))),
                             gradient=ft.LinearGradient([color, ft.Colors.with_opacity(0, color)], stops=[0.25, 0.9]),
                             padding=ft.Padding.symmetric(horizontal=8), alignment=ft.Alignment.CENTER_LEFT),
                left=x0, top=y * row_h, width=max(pos(end) - x0, 6), height=row_h - gap, bgcolor=color,
                image=event_art(e),  # banner art behind the name
                border_radius=min(8, row_h / 3), clip_behavior=ft.ClipBehavior.ANTI_ALIAS, opacity=0.4 if end < now else 1,
                tooltip=e["name"], on_click=lambda _, x=(e, start, end): on_pick(*x)))
    height = max(len(rows) * row_h, row_h)
    now_line = ft.Container(left=pos(now) - 1, top=0, width=2, height=height, bgcolor=ft.Colors.PRIMARY)
    # Flutter pans it natively (mouse drag, touch, trackpad): a scroll_to per drag event from Python lagged.
    # The viewer is exactly as tall as the chart, so the pan can only go sideways.
    chart = ft.Column([header, ft.Stack(bars + [now_line], width=width, height=height)], spacing=8, tight=True)
    return ft.Container(ft.InteractiveViewer(chart, constrained=False, scale_enabled=False),
                        height=36 + 8 + height)


def banner_tile(pool, b, start, end):
    """One event banner: its featured 5★/4★ and how long it runs (or when it starts)."""
    now = datetime.datetime.now().astimezone()
    kind = "Weapon" if pool.startswith("Weapon") else "Character"
    left = end - now
    when = (f"Ends in {left.days}d {left.seconds // 3600}h · {end.astimezone():%d %b %H:%M}" if start <= now
            else f"Starts {start.astimezone():%d %b %H:%M} · until {end.astimezone():%d %b}")
    # NOTE: Chronicled lists a whole region's roster; only the first few are drawn.
    icons = ([item_icon(wiki.name_for(x), kind, 48) for x in b.get("featured", [])[:6]]
             + [item_icon(wiki.name_for(x), kind, 34, 4) for x in b.get("featuredRare", [])[:5]])
    art = wiki.banner_image(b)
    shade = lambda o: ft.Colors.with_opacity(o, ft.Colors.SURFACE_CONTAINER_HIGH)
    # The banner art fills the tile; a left-to-right fade keeps the text readable over it.
    return ft.Container(ft.Container(ft.Column([
        ft.Row([ft.Text(pool, size=14, weight=ft.FontWeight.W_600), pill(f"v{b['version']}") if b.get("version")
                else ft.Container()], spacing=8),
        muted(b["name"], size=12),
        ft.Row(icons, wrap=True, spacing=6, run_spacing=6, vertical_alignment=ft.CrossAxisAlignment.END),
        muted(when, size=12, color=theme.GOLD if start <= now and left.days < 3 else None),
    ], spacing=6), padding=12, gradient=art and ft.LinearGradient(
        begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT, colors=[shade(0.95), shade(0.7), shade(0.1)])),
        border_radius=STYLE["radius"] - 6, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        image=art and ft.DecorationImage(src=wiki.image(art), fit=ft.BoxFit.COVER,
                                         alignment=ft.Alignment.CENTER_RIGHT),
        col={"xs": 12, "md": 6, "xl": 4})


def portrait(src, rarity, size, fallback=ft.Icons.PERSON_ROUNDED):
    """Game icon on its rarity backdrop, like the in-game character list."""
    return ft.Container(ft.Image(src=wiki.image(src), width=size, height=size,
                                 error_content=ft.Icon(fallback, size=size / 2)),
                        width=size, height=size, border_radius=size / 4, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                                   colors=RARITY_BG.get(rarity, ["#4A5068", "#6B7290"])))


def skeleton(n=6, tile=None, height=72):
    """Shimmering placeholders while data loads: n square tiles of `tile` px, or n full-width bars."""
    box = lambda **kw: ft.Container(bgcolor=ft.Colors.ON_SURFACE, border_radius=max(STYLE["radius"] - 8, 8), **kw)
    content = (ft.Row([box(width=tile, height=tile) for _ in range(n)], wrap=True, spacing=10, run_spacing=10)
               if tile else ft.Column([box(height=height) for _ in range(n)], spacing=10, horizontal_alignment=STRETCH))
    return ft.Shimmer(content, base_color=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
                      highlight_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE))


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
    tag = {"won": ("W", theme.WON), "lost": ("L", theme.LOST), "guaranteed": ("G", theme.GOLD)}.get(f["outcome"])
    five = f["rank"] == 5
    parts = [
        item_icon(f["name"], f["item_type"], size=24, rarity=f["rank"]),
        ft.Text(f["name"], size=13, weight=ft.FontWeight.W_600, no_wrap=True, color=None if five else theme.PURPLE),
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
                        gradient=ft.LinearGradient(colors=[theme.GOLD, "#C9965A"]))


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

def pill_select(name, options, value="All", on_select=None, width=150):
    """Filter pill: a rounded dropdown on the raised color."""
    return ft.Dropdown(label=name, value=value, width=width, dense=True, filled=True, border_radius=999,
                       fill_color=ft.Colors.SURFACE_CONTAINER_HIGH, border_width=0, text_size=13,
                       options=options, on_select=on_select)

def search_field(hint, on_change):
    return ft.TextField(hint_text=hint, prefix_icon=ft.Icons.SEARCH_ROUNDED, expand=True, dense=True,
                        filled=True, border_radius=999, fill_color=ft.Colors.SURFACE_CONTAINER_HIGH,
                        border_width=0, on_change=on_change)
def skill_text():
    """Talent text as the Wiki page's Full/Lite button wants it."""
    return wiki.short if db.get_meta(db.connect(), "short_skills") == "1" else str


def panel_tile(*controls, padding=12, **kw):
    """A raised block inside a detail dialog (stat, weapon, artifact, talent)."""
    return ft.Container(ft.Column(list(controls), spacing=4, horizontal_alignment=STRETCH),
                        **{"padding": padding, "border_radius": max(STYLE["radius"] - 6, 8), "bgcolor": STYLE["card_bg"],
                           "border": STYLE["border"], **kw})


def detail_head(page, phone, icon, rarity, name, sub, chips=(), accent=None, art=None, actions=(),
                fallback=ft.Icons.PERSON_ROUNDED):
    """Banner on top of a detail dialog: accent-tinted, the splash art fading in on the right, a big
    portrait, name, subtitle and pills, plus action buttons and a close button in the corner."""
    accent = accent or ft.Colors.PRIMARY
    bg = STYLE["panel"] or ft.Colors.SURFACE
    height = 168 if phone else 196
    art_w = 170 if phone else 340
    layers = [ft.Container(expand=True, gradient=ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
        colors=[ft.Colors.with_opacity(0.42, accent), ft.Colors.with_opacity(0.06, accent)]))]
    if art:
        layers += [
            ft.Container(right=0, top=0, bottom=0, width=art_w, image=ft.DecorationImage(
                src=wiki.image(art), fit=ft.BoxFit.COVER, alignment=ft.Alignment(0, -0.75), opacity=0.55 if phone else 0.95)),
            ft.Container(right=0, top=0, bottom=0, width=art_w, gradient=ft.LinearGradient(  # blend into the tint
                begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT,
                colors=[ft.Colors.with_opacity(0.9, bg), ft.Colors.with_opacity(0, bg)], stops=[0, 0.6]))]
    size = 64 if phone else 88
    layers += [
        ft.Container(ft.Row([portrait(icon, rarity, size, fallback), ft.Column([
            ft.Text(name, size=20 if phone else 26, weight=ft.FontWeight.BOLD, font_family=STYLE["heading_font"],
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            muted(sub, size=12 if phone else 14, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Row(list(chips), wrap=True, spacing=6, run_spacing=4, visible=bool(chips)),
        ], spacing=4, expand=True, alignment=ft.MainAxisAlignment.END)], spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.END),
            left=0, right=0 if phone else art_w / 2, bottom=0, padding=ft.Padding.only(left=20, right=20, bottom=18)),
        ft.Row([*actions, ft.IconButton(ft.Icons.CLOSE_ROUNDED, tooltip="Close", on_click=lambda e: page.pop_dialog(),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.with_opacity(0.6, bg)))],
               spacing=4, top=8, right=8)]
    return ft.Stack(layers, height=height)


def tab_view(sections, selected=0):
    """[(label, [controls])] -> pill tabs over a page that scrolls on its own; one section needs no bar.
    The view's `data` is the open tab. Hand-rolled: ft.Tabs renders as an error box inside an
    AlertDialog (Flet 1.0.3)."""
    page_box = ft.Container(padding=ft.Padding.only(left=20, top=12, right=20, bottom=20), expand=True)
    bar = ft.Row(spacing=6, scroll=ft.ScrollMode.HIDDEN)
    view = ft.Column([ft.Container(bar, padding=ft.Padding.only(left=20, top=14, right=20), visible=len(sections) > 1),
                      page_box], spacing=0, expand=True)

    def show(i, update=True):
        view.data = i
        page_box.content = ft.Column(sections[i][1], spacing=12, scroll=ft.ScrollMode.AUTO, horizontal_alignment=STRETCH)
        for j, b in enumerate(bar.controls):
            b.bgcolor = ft.Colors.PRIMARY if j == i else ft.Colors.SURFACE_CONTAINER_HIGHEST
            b.content.color = ft.Colors.ON_PRIMARY if j == i else ft.Colors.ON_SURFACE_VARIANT
        if update:
            view.update()
    bar.controls = [ft.Container(ft.Text(t, size=13, weight=ft.FontWeight.W_600), border_radius=999,
                                 padding=ft.Padding.symmetric(horizontal=14, vertical=7),
                                 on_click=lambda e, i=i: show(i)) for i, (t, _) in enumerate(sections)]
    show(min(selected, len(sections) - 1), update=False)
    return view


def detail_dialog(page, phone, head, body):
    """Character build / wiki page: `head` (detail_head) over `body` (a Container later filled with
    tab_view), sized to the window; fills a phone screen."""
    w, h = page.width or 400, page.height or 760
    w, h = (w - 16, h - 40) if phone else (min(960, w - 80), min(720, h - 64))
    # Fixed sizes, not expand: AlertDialog measures its content's intrinsic size, which a flex child
    # (and the TabBarView under it) can't report, so the body would render as an error box.
    body.width, body.height = w, h - head.height
    page.show_dialog(ft.AlertDialog(
        content=ft.Column([head, body], spacing=0, tight=True, width=w),
        content_padding=0, inset_padding=ft.Padding.all(8) if phone else None,
        bgcolor=STYLE["panel"] or ft.Colors.SURFACE, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        shape=ft.RoundedRectangleBorder(radius=STYLE["radius"] + 4),
        barrier_color=ft.Colors.with_opacity(0.6, ft.Colors.BLACK)))


def loading_body():
    return ft.Container(ft.Column([skeleton(1, height=40), skeleton(3, height=72)], spacing=12),
                        padding=20)


def priority(items, color=None):
    """Numbered chips in order, "1 Burst > 2 Skill", like a guide's priority line."""
    out = []
    for i, x in enumerate(items):
        out += [ft.Text(">", color=ft.Colors.ON_SURFACE_VARIANT)] * bool(i) + [ft.Container(ft.Row([
            ft.Container(ft.Text(str(i + 1), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.SURFACE),
                         width=18, height=18, border_radius=9, alignment=ft.Alignment.CENTER,
                         bgcolor=color or ft.Colors.PRIMARY),
            ft.Text(x, size=13, weight=ft.FontWeight.W_500)], spacing=6, tight=True),
            padding=ft.Padding.only(left=4, right=10, top=4, bottom=4), border_radius=999,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST)]
    return ft.Row(out, wrap=True, spacing=6, run_spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def guide_view(roles, weapon_rarity=None):
    """paimon.moe build guide laid out like a guide site: role picker, then BUILD, WEAPON (ranked),
    ARTIFACTS (sets, then the main stat of each piece), SUB STATS and TALENT priority, notes."""
    GOLD, PURPLE, WON, _ = theme.accents()
    weapon_rarity = weapon_rarity or {}
    page_col = ft.Column(spacing=12, horizontal_alignment=STRETCH)

    def rank(i):
        return ft.Container(ft.Text("BiS" if i == 0 else f"#{i + 1}", size=11, weight=ft.FontWeight.BOLD,
                                    color=GOLD if i == 0 else ft.Colors.ON_SURFACE_VARIANT), width=34)

    def show(i):
        g = roles[i]
        weapons = []
        for n, w in enumerate(g["weapons"]):
            m = re.fullmatch(r"(.+?)(?: R(\d))?", w)  # "Iron Sting R5", but "Mistsplitter Reforged" stays whole
            base, refine = m.group(1), m.group(2)
            r = weapon_rarity.get(base, 4)
            weapons.append(panel_tile(ft.Row([
                rank(n), item_icon(base, "Weapon", 36, r),
                ft.Column([ft.Text(base, size=13, weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                           muted("★" * r + (f"  ·  R{refine}" if refine else ""), size=11,
                                 color=GOLD if r == 5 else PURPLE if r == 4 else None)], spacing=0, expand=True),
            ], spacing=8), padding=8, col={"xs": 12, "sm": 6, "md": 4}))
        sets = []
        for n, a in enumerate(g["artifacts"]):
            names, _, kind = a.rpartition(" (")
            sets.append(panel_tile(ft.Row([
                rank(n), ft.Text(names, size=13, weight=ft.FontWeight.W_600, expand=True),
                pill("4-Piece" if kind == "4)" else "2 + 2", WON)], spacing=8), padding=10, col={"xs": 12, "md": 6}))
        mains = [panel_tile(muted(k.upper(), size=11, weight=ft.FontWeight.W_600),
                            ft.Text(v, size=14, weight=ft.FontWeight.W_600), col={"xs": 12, "sm": 4})
                 for k, _, v in (m.partition(": ") for m in g["main"])]
        page_col.controls = [
            label("Build"),
            ft.Row([ft.Text(g["role"].title().replace("Dps", "DPS"), size=18, weight=ft.FontWeight.BOLD)]
                   + [pill("Recommended", WON)] * g["recommended"], spacing=8),
            label("Weapon"), ft.ResponsiveRow(weapons, spacing=8, run_spacing=8),
            label("Artifacts"), ft.ResponsiveRow(sets, spacing=8, run_spacing=8),
            ft.ResponsiveRow(mains, spacing=8, run_spacing=8),
            label("Sub stats"), priority(g["subs"]),
            label("Talent priority"), priority(g["talents"], GOLD),
        ] + ([label("Notes"), panel_tile(muted(g["note"], size=13, selectable=True))] if g.get("note") else [])

    show(0)
    if len(roles) == 1:
        return [page_col]

    def pick(e):
        show(int(e.control.selected[0]))
        page_col.update()
    return [ft.Row([ft.SegmentedButton(selected=["0"], show_selected_icon=False, on_change=pick, segments=[
        ft.Segment(str(i), label=g["role"].title().replace("Dps", "DPS")) for i, g in enumerate(roles)])], scroll=ft.ScrollMode.HIDDEN),
        page_col]
