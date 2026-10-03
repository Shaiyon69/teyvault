"""Game catalogue for the Wiki tab: HoYoLAB's own wiki (characters, weapons, artifacts, enemies) and
paimon.moe's achievement list. Both are public, fetched page by page and cached in the `meta` table."""
import datetime
import json
import time
import urllib.request

from teyvat import db
from teyvat.hoyolab import SSL_CONTEXT, UA, request

WIKI_LIST_URL = "https://sg-wiki-api.hoyolab.com/hoyowiki/genshin/wapi/get_entry_page_list"
WIKI_ENTRY_URL = "https://wiki.hoyolab.com/pc/genshin/entry/{}"
ACHIEVEMENTS_URL = "https://cdn.jsdelivr.net/gh/MadeBaruna/paimon-moe@main/src/data/achievement/en.json"
MENUS = {"Characters": 2, "Weapons": 4, "Artifacts": 5, "Enemies": 7}
PAGE_SIZE = 50  # the API rejects more
PAGE_DELAY_S = 1
CACHE_DAYS = 7
# filter_values keys -> what the filter bar calls them (unknown keys get a title-cased fallback)
LABELS = {
    "character_vision": "Element", "character_weapon": "Weapon", "character_rarity": "Rarity",
    "character_region": "Region", "character_property": "Ascension stat",
    "weapon_type": "Type", "weapon_rarity": "Rarity", "weapon_property": "Substat",
    "filter_key_43": "Rarity", "reliquary_effect": "Set bonus", "enemy_and_monster_type": "Type",
}


def label(key) -> str:
    return LABELS.get(key) or key.replace("_", " ").title()


def _cached(conn, key, fetch, refresh=False):
    """Cached JSON under meta[key]: {"date": iso, "data": ...}, refetched after CACHE_DAYS."""
    hit = json.loads(db.get_meta(conn, key) or "null")
    fresh = hit and datetime.date.fromisoformat(hit["date"]) > datetime.date.today() - datetime.timedelta(CACHE_DAYS)
    if hit and fresh and not refresh:
        return hit["data"]
    try:
        data = fetch()
    except Exception:
        if hit:  # offline: an old catalogue beats none
            return hit["data"]
        raise
    db.set_meta(conn, key, json.dumps({"date": datetime.date.today().isoformat(), "data": data}))
    return data


def _fetch_menu(menu_id, sleep=time.sleep) -> list[dict]:
    out, page = [], 1
    while True:
        data = request(WIKI_LIST_URL, body={"menu_id": str(menu_id), "page_num": page, "page_size": PAGE_SIZE,
                                            "use_es": True},
                       referer="https://wiki.hoyolab.com/", headers={"x-rpc-language": "en-us"})["data"]
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


def entries(conn, category, refresh=False) -> list[dict]:
    menu = MENUS[category]
    _icons.clear()
    return _cached(conn, f"wiki:{menu}", lambda: _fetch_menu(menu), refresh)


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
             if "rarity" in k or k == "filter_key_43" for v in vs if "★" in v or v[:1].isdigit()]
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


def _get_json(url):
    """Plain JSON file (no HoYoLAB retcode envelope)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as resp:
        return json.load(resp)


_icons = {}


def icon_for(name) -> str | None:
    """HoYoLAB's icon for a character or weapon name, from the cached wiki lists (no request)."""
    if "" not in _icons:  # loaded marker; entries() clears it after a refetch
        _icons[""] = None
        conn = db.connect()
        for menu in (MENUS["Characters"], MENUS["Weapons"]):
            hit = json.loads(db.get_meta(conn, f"wiki:{menu}") or "null")
            _icons.update({e["name"]: e["icon"] for e in hit["data"]} if hit else {})
    return _icons.get(name)
