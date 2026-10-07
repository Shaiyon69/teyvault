"""Events tab: paimon.moe's event timeline as a month calendar or a Gantt chart."""
import datetime

import flet as ft

from teyvat import db, wiki
from teyvat.gui import theme
from teyvat.gui.app import EVENTS
from teyvat.gui.theme import STRETCH
from teyvat.gui.widgets import card, label, month_calendar, muted, skeleton, timeline_chart

# name fragment -> what the event is; first match wins, so weapon banners come before character ones.
# Banners named without "Banner" are matched by banners.js's names (event_kind); the ones paimon.moe hasn't
# added there yet are listed here.
KINDS = [("epitome invocation", "Weapon banner"), ("chronicled", "Chronicled banner"), ("banner", "Character banner"),
         ("surging ballad", "Character banner"),
         ("battle pass", "Battle Pass"), ("spiral abyss", "Endgame"), ("imaginarium", "Endgame"),
         ("stygian", "Endgame"), ("daily login", "Login event"), ("maintenance", "Maintenance"), ("version", "Update")]


BANNER_KINDS = {"characters": "Character banner", "weapons": "Weapon banner", "chronicled": "Chronicled banner"}


def event_kind(e, banners=None):
    """What the event is, from its name (paimon.moe's timeline has no type field).
    `banners`: banners.js's {pool: [banner, ...]}, to recognise banners named without "Banner"."""
    n = e["name"].lower()
    named = next((BANNER_KINDS.get(pool, "Banner") for pool, bs in (banners or {}).items()
                  for b in bs if b["name"].lower() in n), None)
    return named or next((kind for key, kind in KINDS if key in n), "In-game event")


def build(app):
    page, phone, active_role = app.page, app.phone, app.active_role
    GOLD = theme.accents()[0]

    ev = {"events": [], "rows": [], "patches": [], "region": None, "month": None, "selected": None,
          "banners": {}, "mode": db.get_meta(db.connect(), "events_view", "calendar"), "h": None}
    month_label = ft.Text(size=16, weight=ft.FontWeight.W_600)
    month_nav = ft.Row([
        ft.IconButton(ft.Icons.CHEVRON_LEFT_ROUNDED, tooltip="Previous month", on_click=lambda _: shift_month(-1)),
        ft.IconButton(ft.Icons.TODAY_ROUNDED, tooltip="Today", on_click=lambda _: pick_day(datetime.date.today())),
        ft.IconButton(ft.Icons.CHEVRON_RIGHT_ROUNDED, tooltip="Next month", on_click=lambda _: shift_month(1)),
    ], spacing=0)

    def set_mode(e):
        ev["mode"] = e.control.selected[0]
        db.set_meta(db.connect(), "events_view", ev["mode"])
        if ev["events"]:
            render_events()
        page.update()

    mode_pick = ft.SegmentedButton(selected=[ev["mode"]], show_selected_icon=False, on_change=set_mode, segments=[
        ft.Segment("calendar", label=None if phone else "Calendar", icon=ft.Icons.CALENDAR_MONTH_ROUNDED),
        ft.Segment("timeline", label=None if phone else "Timeline", icon=ft.Icons.VIEW_TIMELINE_ROUNDED)])
    calendar_body = ft.Column([skeleton(5, height=64 if phone else 84)], horizontal_alignment=STRETCH,
                              expand=not phone)
    calendar_hint = muted("", size=13)

    def sized(e):
        """PC: refit the Gantt when the card's height changes (window resize, first layout)."""
        if ev["h"] is None or abs(e.height - ev["h"]) > 4:
            ev["h"] = e.height
            if ev["mode"] == "timeline" and ev["events"]:
                render_events()
                page.update()
    if not phone:
        calendar_body.on_size_change = sized
    calendar_card = card(ft.Row([month_label, ft.Container(expand=True), month_nav, mode_pick],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER),
                         calendar_hint, calendar_body, title="Events", expand=None if phone else 2)
    # PC: the view sits outside the page scroll (like the Dashboard), so both cards stretch to the window's
    # height; the grid's weeks share it and the details scroll inside their card.
    event_body = ft.Column([skeleton(3, height=40)], spacing=8, horizontal_alignment=STRETCH,
                           expand=not phone, scroll=None if phone else ft.ScrollMode.AUTO)
    patch_title = ft.Text(size=15, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.END)
    patch_dates = muted("", size=12, text_align=ft.TextAlign.END)
    event_card = card(ft.Row([label("Event details"), ft.Column([patch_title, patch_dates], spacing=0,
                                                               horizontal_alignment=ft.CrossAxisAlignment.END)],
                             alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                             vertical_alignment=ft.CrossAxisAlignment.START),
                      event_body, expand=None if phone else 1)
    if not phone:  # let the cards' columns pass the stretched height down to the grid and the list
        calendar_card.content.expand = event_card.content.expand = True

    def event_info(e, start, end):
        """Name, art, dates and time left of one timeline event."""
        now = datetime.datetime.now().astimezone()
        left = end - now
        when = (f"Ended {end.astimezone():%d %b}" if left.total_seconds() < 0 else
                f"Ends in {left.days}d {left.seconds // 3600}h" if start <= now else
                f"Starts in {(start - now).days}d {(start - now).seconds // 3600}h")
        art = wiki.event_image(e)
        return [
            ft.Image(src=wiki.image(art), border_radius=10, fit=ft.BoxFit.COVER, height=110,
                     error_content=ft.Container()) if art else ft.Container(),
            label(event_kind(e, ev["banners"])),
            ft.Text(e["name"], size=16, weight=ft.FontWeight.W_600),
            ft.Text(when, size=13, weight=ft.FontWeight.W_600, color=GOLD),
            muted(f"{start.astimezone():%d %b %H:%M} – {end.astimezone():%d %b %H:%M}", size=12),
            muted(e.get("description") or "", size=13, visible=bool(e.get("description"))),
            ft.Row([ft.OutlinedButton("HoYoLAB article", icon=ft.Icons.OPEN_IN_NEW_ROUNDED, url=e["url"])])
            if e.get("url") else ft.Container(),
        ]

    def open_event(e, start, end):
        body = ft.Column(event_info(e, start, end), tight=True, spacing=8, horizontal_alignment=STRETCH)
        page.show_dialog(ft.BottomSheet(ft.Container(body, padding=21)) if phone else
                         ft.AlertDialog(content=ft.Container(body, width=420), scrollable=True))

    def event_row(e, start, end):
        now = datetime.datetime.now().astimezone()
        art = wiki.event_image(e)
        left = end - now
        status = ("Ended" if left.total_seconds() < 0 else f"{left.days}d {left.seconds // 3600}h left" if start <= now
                  else f"Starts in {(start - now).days}d")
        return ft.Container(ft.Row([
            ft.Container(width=64, height=40, border_radius=8, bgcolor=e.get("color", GOLD),
                         image=art and ft.DecorationImage(src=wiki.image(art), fit=ft.BoxFit.COVER)),
            ft.Column([
                ft.Text(e["name"], size=13, weight=ft.FontWeight.W_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                # numeric dates stay short enough to keep their own column instead of wrapping under the status
                ft.Row([ft.Text(spans=[ft.TextSpan(f"{event_kind(e, ev['banners'])} · ",
                                                   ft.TextStyle(color=GOLD, weight=ft.FontWeight.W_600)),
                                       ft.TextSpan(status)], size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                        muted(f"{start.astimezone():%d/%m} – {end.astimezone():%d/%m}", size=12, no_wrap=True)],
                       spacing=8),
                muted(e.get("description") or "", size=12, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                      visible=bool(e.get("description"))),
            ], spacing=2, expand=True),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START), padding=6, border_radius=10, opacity=0.45 if end < now else 1,
            on_click=lambda _: open_event(e, start, end))

    def show_event(e, start, end):
        """Timeline tap: the details card on PC, a sheet on phones."""
        if phone:
            return open_event(e, start, end)
        event_body.controls = event_info(e, start, end)
        page.update()

    def patch_of(d):
        local = lambda dt: dt.astimezone().date()
        return next((p for p in ev["patches"] if local(p[1]) <= d <= local(p[2] - datetime.timedelta(seconds=1))), None)

    def render_events():
        d, patch = ev["selected"], patch_of(ev["selected"])
        timeline = ev["mode"] == "timeline"
        month_label.value = "Next weeks" if timeline else f"{ev['month']:%B %Y}"
        month_nav.visible = not timeline
        calendar_hint.value = ("From paimon.moe, in your local time. " +
                               ("Drag to scroll, tap an event for its details." if timeline else
                                "Event art marks the days events start and end. Tap a day for its patch's events."))
        # PC: the Gantt's rows squeeze into the card's measured height, like the grid's weeks share it
        calendar_body.controls = [timeline_chart(ev["rows"], show_event, height=None if phone else ev["h"]) if timeline
                                  else month_calendar(ev["month"], ev["events"], d, pick_day, compact=phone)]
        if patch:
            version, start, end = patch
            patch_title.value = f"Version {version}"
            patch_dates.value = f"{start.astimezone():%d %b} – {end.astimezone():%d %b %Y}"
            on = [x for x in ev["events"] if x[1] < end and x[2] > start]
        else:  # past the last announced banner, or no banner data: just that day
            patch_title.value, patch_dates.value = f"{d:%A %d %B}", ""
            day = datetime.datetime.combine(d, datetime.time()).astimezone()
            on = [x for x in ev["events"] if x[1] < day + datetime.timedelta(1) and x[2] > day]
        event_body.controls = ([event_row(*x) for x in sorted(on, key=lambda x: (x[1], x[2]))]
                                      or [muted("No events.", size=13)])

    def pick_day(d):
        if not ev["events"] and not ev["patches"]:
            return
        ev["selected"], ev["month"] = d, d.replace(day=1)
        render_events()
        page.update()

    def shift_month(n):
        if ev["month"]:
            m = ev["month"].month - 1 + n
            ev["month"] = datetime.date(ev["month"].year + m // 12, m % 12 + 1, 1)
            render_events()
            page.update()

    def load_timeline():
        """Worker thread. Times follow the active game account's server (Asia's clock if signed out)."""
        role = active_role()
        region = role and role["region"]
        conn = db.connect()
        try:
            rows = wiki.timeline(conn)
            wiki.cache_images(wiki.event_image(e) for row in rows for e in row)
        except Exception as ex:
            calendar_body.controls, event_body.controls = [muted(f"Could not load the events: {ex}")], []
            page.update()
            return
        try:
            ev["banners"] = wiki.banners(conn)
            ev["patches"] = wiki.patches(ev["banners"], region)
        except Exception:
            ev["patches"] = []  # the details card falls back to the tapped day's events
        ev["rows"] = [[(e, *wiki.event_times(e, region)) for e in row] for row in rows]
        # longest first among same-day starts, so a day's chips keep the same order across the month
        ev["events"] = sorted((x for row in ev["rows"] for x in row), key=lambda x: (x[1].date(), x[1] - x[2]))
        ev["selected"] = datetime.date.today()
        ev["month"] = ev["selected"].replace(day=1)
        render_events()
        page.update()

    app.load_timeline = load_timeline
    return ft.Column([app.page_head(EVENTS), *([calendar_card, event_card] if phone else [ft.Row(
        [calendar_card, event_card], spacing=16, expand=True, vertical_alignment=STRETCH)])],
        spacing=16, horizontal_alignment=STRETCH, expand=not phone)
