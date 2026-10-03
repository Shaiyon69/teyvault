"""Game catalogue for the Wiki tab: HoYoLAB's own wiki (characters, weapons, artifacts, enemies, collectibles) and
paimon.moe's achievement list, event timeline and banners. All public, fetched page by page and cached in the `meta`
table. Caches are checked daily, so a new patch shows up without pressing refresh."""
import ast
import datetime
import functools
import hashlib
import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from teyvat import db, wish
from teyvat.hoyolab import SSL_CONTEXT, UA, request

WIKI_LIST_URL = "https://sg-wiki-api.hoyolab.com/hoyowiki/genshin/wapi/get_entry_page_list"
WIKI_ENTRY_URL = "https://wiki.hoyolab.com/pc/genshin/entry/{}"
ENTRY_API_URL = "https://sg-wiki-api-static.hoyolab.com/hoyowiki/genshin/wapi/entry_page"
ACHIEVEMENTS_URL = "https://cdn.jsdelivr.net/gh/MadeBaruna/paimon-moe@main/src/data/achievement/en.json"
TIMELINE_URL = "https://cdn.jsdelivr.net/gh/MadeBaruna/paimon-moe@main/src/data/timeline.js"
BANNERS_URL = "https://cdn.jsdelivr.net/gh/MadeBaruna/paimon-moe@main/src/data/banners.js"
# Each server's clock (fixed offsets, no daylight saving).
SERVER_UTC = {"os_usa": -5, "os_euro": 1, "os_asia": 8, "os_cht": 8}
MENUS = {"Characters": 2, "Weapons": 4, "Artifacts": 5, "Enemies": 7}
# Shown together as "Collectibles", told apart by a "Type" filter.
COLLECTIBLES = {"Namecards": 35, "Wings": 33, "Outfits": 34}
# Wish pools in paimon.moe's banners.js -> what the game calls them.
BANNER_POOLS = {"characters": "Character Event Wish", "weapons": "Weapon Event Wish", "chronicled": "Chronicled Wish"}
PAGE_SIZE = 50  # the API rejects more
PAGE_DELAY_S = 1
CACHE_DAYS = 1
# filter_values keys -> what the filter bar calls them (unknown keys get a title-cased fallback)
LABELS = {
    "character_vision": "Element", "character_weapon": "Weapon", "character_rarity": "Rarity",
    "character_region": "Region", "character_property": "Ascension stat",
    "weapon_type": "Type", "weapon_rarity": "Rarity", "weapon_property": "Substat",
    "filter_key_43": "Rarity", "reliquary_effect": "Set bonus", "enemy_and_monster_type": "Type",
    "collectible": "Type", "filter_key_52": "Rarity",
}


def label(key) -> str:
    return LABELS.get(key) or key.replace("_", " ").title()


def _cached(conn, key, fetch, refresh=False, days=CACHE_DAYS, unchanged=None):
    """Cached JSON under meta[key]: {"date": iso, "data": ...}, refetched after `days`.
    `unchanged(data)`, when given, is a cheap check that skips the full refetch while it holds."""
    hit = json.loads(db.get_meta(conn, key) or "null")
    fresh = hit and datetime.date.fromisoformat(hit["date"]) > datetime.date.today() - datetime.timedelta(days)
    if hit and fresh and not refresh:
        return hit["data"]
    try:
        data = hit["data"] if hit and not refresh and unchanged and unchanged(hit["data"]) else fetch()
    except Exception:
        if hit:  # offline: an old catalogue beats none
            return hit["data"]
        raise
    db.set_meta(conn, key, json.dumps({"date": datetime.date.today().isoformat(), "data": data}))
    return data


def _page(menu_id, page, size=PAGE_SIZE) -> dict:
    return request(WIKI_LIST_URL, body={"menu_id": str(menu_id), "page_num": page, "page_size": size, "use_es": True},
                   referer="https://wiki.hoyolab.com/", headers={"x-rpc-language": "en-us"})["data"]


def _fetch_menu(menu_id, sleep=time.sleep) -> list[dict]:
    out, page = [], 1
    while True:
        data = _page(menu_id, page)
        out += [slim(e) for e in data["list"]]
        if len(out) >= int(data["total"]) or not data["list"]:
            return out
        page += 1
        sleep(PAGE_DELAY_S)


def slim(e) -> dict:
    """Keep what the tab shows: id, name, icon, {filter: [values]}, element icons, searchable text."""
    df = e.get("display_field") or {}
    return {
        "id": e["entry_page_id"], "name": e["name"], "icon": e["icon_url"],
        "filters": {k: v["values"] for k, v in (e.get("filter_values") or {}).items()},
        "icons": {t["value"]: t["icon"] for v in (e.get("filter_values") or {}).values()
                  for t in v.get("value_types") or [] if t.get("icon")},
        "desc": " ".join(x for x in (e.get("desc"), df.get("two_set_effect"), df.get("four_set_effect"),
                                     df.get("single_set_effect")) if x),
    }


def _menu(conn, menu, refresh=False) -> list[dict]:
    """One menu's entries. Once a day a one-entry request compares the total, and only a new count
    (a patch added entries) downloads the whole list again."""
    # NOTE: an entry edited in place (same count) waits for the refresh button.
    return _cached(conn, f"wiki:{menu}", lambda: _fetch_menu(menu), refresh,
                   unchanged=lambda old: len(old) == int(_page(menu, 1, 1)["total"]))


def entries(conn, category, refresh=False) -> list[dict]:
    _icons.clear()
    if category == "Collectibles":
        return [{**e, "filters": {"collectible": [kind], **e["filters"]}}
                for kind, menu in COLLECTIBLES.items() for e in _menu(conn, menu, refresh)]
    return _menu(conn, MENUS[category], refresh)


def filters(items) -> dict[str, list[str]]:
    """{filter key: sorted distinct values} across the entries."""
    out = {}
    for e in items:
        for k, vs in e["filters"].items():
            out.setdefault(k, set()).update(vs)
    return {k: sorted(v) for k, v in out.items()}


def rarity(e) -> int:
    """5 for "5-Star" / "★★★★★", 0 when the entry has none (enemies)."""
    stars = [v.count("★") or int(v[0]) for k, vs in e["filters"].items()
             for v in vs if "★" in v or ("rarity" in k and v[:1].isdigit())]
    return max(stars, default=0)


def text(rich) -> str:
    """Wiki HTML -> plain text: <br> and paragraphs become line breaks, tags dropped, entities decoded."""
    rich = re.sub(r"<br\s*/?>|</p>\s*<p[^>]*>", "\n", rich or "")
    return html.unescape(re.sub(r"<[^>]+>", "", rich)).strip()


def short(desc) -> str:
    """Lite skill text: the first sentence of each part ("Charged Attack", "Hold", ...), else of the whole.
    Lore lines and the later sentences go; a list the kept sentence introduces ("effects:") stays."""
    lines = [x.strip() for x in desc.splitlines() if x.strip()]
    heading = lambda x: len(x) <= 40 and not x.endswith((".", "!", "?", ":", "%", ")")) and not x.startswith("·")
    # with sub-headings, text before the first one is flavor
    out, want, listing = [], not any(map(heading, lines)), False
    for x in lines:
        if heading(x):
            out.append(x)
            want, listing = True, False
        elif want:
            out.append(re.match(r".+?[.!?](?=\s|$)|.+", x).group())
            want, listing = False, out[-1].endswith(":")
        elif listing and x.startswith("·"):
            out.append(x)
        else:
            listing = False
    return "\n".join(out) or desc


def _value(v) -> str:
    """A baseInfo value: rich text, or a "$[...]$" link list to other entries (names kept)."""
    if v.startswith("$[") and v.endswith("]$"):
        return ", ".join(r.get("name") or r.get("nickname") or "" for r in json.loads(v[1:-1]))
    return text(v)


def slim_entry(p) -> dict:
    """One wiki page -> {name, icon, image, desc, sections: [{title, rows: [[name, text, icon]]}]}.
    Keeps the readable modules (attributes, set bonus, talents, constellations, stats, lore); skips
    voice lines, videos and material lists."""
    out = {"name": p["name"], "icon": p["icon_url"], "image": "", "desc": text(p["desc"]), "sections": []}
    for mod in p["modules"]:
        for comp in mod["components"]:
            d, cid, title = json.loads(comp["data"] or "null"), comp["component_id"], mod["name"]
            if not d:
                continue
            rows = []
            if cid == "baseInfo":
                rows = [[x["key"], ", ".join(_value(v) for v in x["value"]), ""] for x in d["list"] if x["key"] != "Name"]
            elif cid == "reliquary_set_effect":
                rows = [[k, d[f], ""] for k, f in (("1-Piece", "single_set_effect"), ("2-Piece", "two_set_effect"),
                                                   ("4-Piece", "four_set_effect")) if d.get(f)]
            elif cid == "artifact_list":
                rows = [[x["title"], text(x.get("desc")), x.get("icon_url", "")]
                        for x in d.values() if isinstance(x, dict) and x.get("title")]
            elif cid == "talent":
                rows = [[x["title"], text(x["desc"]), x.get("icon_url", "")] for x in d["list"]]
            elif cid == "summaryList":
                rows = [[x["name"], text(x["desc"]), x.get("icon_url", "")] for x in d["list"]]
            elif cid == "ascension" and d.get("list"):
                top = d["list"][-1]  # the max level
                title = f"Stats at {top['key']}"
                head, *body = top["combatList"]  # first row names the columns; "-" = no value at max level
                for x in body:
                    vals = {re.sub(r" (before|after) Ascension", "", h): v
                            for h, v in zip(head["values"], x["values"]) if v != "-"}
                    # characters: one stat per row; weapons: an unnamed row of ATK + substat
                    rows += ([[x["key"], list(vals.values())[-1], ""]] if x["key"] and vals
                             else [[h, v, ""] for h, v in vals.items()])
            elif cid == "story":
                rows = [[x.get("title", ""), text(x["desc"]), ""] for x in d["list"] if x.get("desc")]
            elif cid == "gallery_character":
                out["image"] = d.get("pic") or next((x["img"] for x in d.get("list", []) if x.get("img")), "")
            if rows:
                last = out["sections"][-1] if out["sections"] else None
                if last and last["title"] == title:
                    last["rows"] += rows
                else:
                    out["sections"].append({"title": title, "rows": rows})
    return out


def entry(conn, entry_id, refresh=False) -> dict:
    """One wiki page, shown in the app instead of the website. Kept a week, read offline after that."""
    fetch = lambda: slim_entry(request(ENTRY_API_URL, params={"entry_page_id": entry_id},
                                       referer="https://wiki.hoyolab.com/",
                                       headers={"x-rpc-language": "en-us"})["data"]["page"])
    return _cached(conn, f"wiki:entry:{entry_id}", fetch, refresh, days=7)


def prefetch_entries(conn, ids, sleep=time.sleep) -> list[str]:
    """Download wiki pages for offline reading, spaced like list pages; ones fetched this week cost no
    request. Returns their image URLs for cache_images."""
    urls = []
    for i in ids:
        before = db.get_meta(conn, f"wiki:entry:{i}")
        try:
            d = entry(conn, i)
        except Exception:
            continue  # offline or a broken page: it loads on open instead
        urls += [d["image"]] + [x[2] for sec in d["sections"] for x in sec["rows"]]
        if db.get_meta(conn, f"wiki:entry:{i}") != before:
            sleep(PAGE_DELAY_S)
    return urls


def flatten_achievements(raw) -> list[dict]:
    """paimon.moe groups tiered achievements in a nested list; flatten them, keeping the category."""
    out = []
    for cat in raw.values():
        for a in cat["achievements"]:
            for x in a if isinstance(a, list) else [a]:
                out.append({"id": x["id"], "name": x["name"], "desc": x.get("desc", ""),
                            "reward": x.get("reward", 0), "ver": x.get("ver", ""), "category": cat["name"]})
    return out


def achievements(conn, refresh=False) -> list[dict]:
    return _cached(conn, "wiki:achievements",
                   lambda: flatten_achievements(_get_json(ACHIEVEMENTS_URL)), refresh)


def parse_js(js):
    """paimon.moe's `export const x = <literal>;` data modules (timeline.js, banners.js) -> Python.
    Prettier puts every key at the start of a line, so quoting those makes it a Python literal."""
    # NOTE: breaks if paimon.moe adds JS expressions (e.g. `'a' + 'b'`); then literal_eval raises
    # and the stale cache is kept.
    body = js[js.index("=") + 1:].strip().rstrip(";")
    body = re.sub(r"^\s*//.*\n", "", body, flags=re.M)  # commented-out entries
    body = re.sub(r"^(\s*)(\w+):", r'\1"\2":', body, flags=re.M)
    body = re.sub(r'(":\s*)(true|false)(?=,?$)', lambda m: m[1] + m[2].title(), body, flags=re.M)
    return ast.literal_eval(body)


def timeline(conn, refresh=False) -> list[list[dict]]:
    """Rows of events; events in a row never overlap."""
    return _cached(conn, "wiki:timeline", lambda: parse_js(_get(TIMELINE_URL).decode()), refresh)


def banners(conn, refresh=False) -> dict:
    """Banner history and the current/next ones, featured items as paimon.moe ids. Only the event pools are kept."""
    return _cached(conn, "wiki:banners",
                   lambda: {k: v for k, v in parse_js(_get(BANNERS_URL).decode()).items() if k in BANNER_POOLS},
                   refresh)


def current_banners(data, region=None, now=None) -> list[tuple[str, dict, datetime.datetime, datetime.datetime]]:
    """(pool name, banner, start, end) for each event pool: the banner running now, or else the next one.
    Pools with nothing running or announced (Chronicled between its runs) are left out."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    out = []
    for pool, name in BANNER_POOLS.items():
        ahead = sorted((t for t in ((b, *event_times(b, region)) for b in data.get(pool, [])) if t[2] > now),
                       key=lambda t: t[1])
        if ahead:
            out.append((name, *ahead[0]))
    return out


def event_times(e, region=None) -> tuple[datetime.datetime, datetime.datetime]:
    """Aware start/end. paimon.moe writes times in UTC+8, except `timezoneDependent` events
    (patch-day starts, resets), which follow the player's own server clock."""
    hours = SERVER_UTC.get(region, 8) if e.get("timezoneDependent") else 8
    tz = datetime.timezone(datetime.timedelta(hours=hours))
    return tuple(datetime.datetime.fromisoformat(e[k]).replace(tzinfo=tz) for k in ("start", "end"))


def _get(url) -> bytes:
    # Wiki icon URLs can hold spaces or CJK ("Hu Tao_icon.png", "笼钓瓶一心.png"); urllib needs them escaped.
    req = urllib.request.Request(urllib.parse.quote(url, safe=":/?&=%#+,;@~"), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as resp:
        return resp.read()


def _get_json(url):
    """Plain JSON file (no HoYoLAB retcode envelope)."""
    return json.loads(_get(url))


_icons = {}


def name_for(paimon_id) -> str:
    """Display name for a paimon.moe id ("kuki_shinobu") from the cached wiki lists, else a title-cased guess."""
    icon_for("")  # loads the names
    return next((n for n in _icons if n and wish.slug(n) == paimon_id), paimon_id.replace("_", " ").title())


def icon_for(name) -> str | None:
    """HoYoLAB's icon for a character or weapon name, from the cached wiki lists (no request)."""
    if "" not in _icons:  # loaded marker; entries() clears it after a refetch
        _icons[""] = None
        conn = db.connect()
        for menu in (MENUS["Characters"], MENUS["Weapons"]):
            hit = json.loads(db.get_meta(conn, f"wiki:{menu}") or "null")
            _icons.update({e["name"]: e["icon"] for e in hit["data"]} if hit else {})
    return _icons.get(name)


@functools.cache
def _image_dir() -> Path:
    return db.default_path().parent / "images"


def _image_path(url) -> Path:
    suffix = Path(urllib.parse.urlsplit(url).path).suffix[:5] or ".img"  # Flutter sniffs the format anyway
    return _image_dir() / (hashlib.sha1(url.encode()).hexdigest() + suffix)


def image(url):
    """The downloaded copy of a remote image (see cache_images) as a local path, else the URL itself.
    Flet shows absolute file paths directly, so cached icons need no network (offline, flaky phone data)."""
    if url:
        path = _image_path(url)
        if path.exists():
            return str(path)
    return url


def cache_images(urls):
    """Download the images not cached yet, one at a time. Failures (offline, 404) are skipped:
    the Image's error_content still covers them."""
    # NOTE: never evicted; a whole catalogue is tens of MB. Add a size cap if phones complain.
    for url in dict.fromkeys(u for u in urls if u):
        path = _image_path(url)
        if path.exists():
            continue
        try:
            data = _get(url)
        except Exception:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(f"{path.name}.{threading.get_ident()}.part")  # threads may race on one URL
        part.write_bytes(data)
        part.replace(path)


def icon_urls() -> list[str]:
    """Every cached character and weapon icon URL, for prefetching."""
    icon_for("")
    return [u for u in _icons.values() if u]
