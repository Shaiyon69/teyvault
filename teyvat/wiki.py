"""Game catalogue for the Wiki tab: HoYoLAB's own wiki (characters, weapons, artifacts, enemies, collectibles) and
paimon.moe's achievement list, event timeline and banners. All public, fetched page by page and cached in the `meta`
table. Caches are checked daily, so a new patch shows up without pressing refresh."""
import ast
import datetime
import functools
import hashlib
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
    req = urllib.request.Request(url, headers={"User-Agent": UA})
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
