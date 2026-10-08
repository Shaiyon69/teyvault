import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from teyvat import db, wiki, wish
from teyvat.gui import widgets

WEAPON = {"entry_page_id": "1", "name": "Aqua Simulacra", "icon_url": "x.png", "desc": "", "display_field": {},
          "filter_values": {"weapon_type": {"values": ["Bow"], "value_types": [{"value": "Bow", "icon": ""}]},
                            "weapon_rarity": {"values": ["5-Star"], "value_types": []}}}
ARTIFACT = {"entry_page_id": "2", "name": "Gladiator's Finale", "icon_url": "y.png", "desc": "",
            "display_field": {"two_set_effect": "ATK +18%."},
            "filter_values": {"filter_key_43": {"values": ["★★★★", "★★★★★"], "value_types": []}}}


class TestWiki(unittest.TestCase):
    def test_slim_filters_and_rarity(self):
        w, a = wiki.slim(WEAPON), wiki.slim(ARTIFACT)
        self.assertEqual(wiki.filters([w, a]), {"weapon_type": ["Bow"], "weapon_rarity": ["5-Star"],
                                                 "filter_key_43": ["★★★★", "★★★★★"]})
        self.assertEqual((wiki.rarity(w), wiki.rarity(a)), (5, 5))
        self.assertIn("ATK +18%", a["desc"])
        self.assertEqual(wiki.label("weapon_type"), "Type")
        self.assertEqual(wiki.label("new_key"), "New Key")

    def test_slim_entry_page(self):
        comp = lambda cid, data: {"component_id": cid, "data": json.dumps(data)}
        page = {"name": "Bow", "icon_url": "i.png", "desc": "A bow<br>&#39;nice&#39;", "modules": [
            {"name": "Attributes", "components": [comp("baseInfo", {"list": [
                {"key": "Name", "value": ["Bow"]}, {"key": "Region", "value": ["<p>Snezhnaya</p>"]},
                {"key": "Namecard", "value": ['$[{"ep_id":1,"name":"Card"}]$']}]})]},
            {"name": "Ascend", "components": [comp("ascension", {"list": [{"key": "Lv.90", "combatList": [
                {"key": "", "values": ["ATK before Ascension", "ATK after Ascension", "CRIT Rate"]},
                {"key": "", "values": ["510", "-", "27.6%"]}]}]})]},
            {"name": "Loot", "components": [comp("drop_material", {"list": [
                '$[{"ep_id":1,"name":"Mora","icon":"m.png"}]$', '$[{"ep_id":2,"nickname":"x"}]$']})]},
            {"name": "Properties", "components": [comp("customize", {"data": '<p><span>Teyvat: </span>'
                                                                       '<custom-map url="https://map/2"></custom-map></p>'})]},
            {"name": "Gallery", "components": [comp("gallery_character", {"pic": "splash.png", "list": []})]},
            {"name": "Voice-Over", "components": [comp("voice", {"list": []})]}]}
        e = wiki.slim_entry(page)
        self.assertEqual((e["desc"], e["image"]), ("A bow\n'nice'", "splash.png"))
        self.assertEqual(e["sections"], [
            {"title": "Attributes", "rows": [["Namecard", "Card", ""]]},
            {"title": "Where to find", "rows": [["Region", "Snezhnaya", ""], ["Drops Mora", "", "m.png"]]},
            {"title": "Stats at Lv.90", "rows": [["ATK", "510", ""], ["CRIT Rate", "27.6%", ""]]}])

    def test_flatten_tiered_achievements(self):
        raw = {"0": {"name": "Wonders", "achievements": [
            {"id": 1, "name": "One", "reward": 5},
            [{"id": 2, "name": "Tier", "reward": 5}, {"id": 3, "name": "Tier", "reward": 10}]]}}
        flat = wiki.flatten_achievements(raw)
        self.assertEqual([a["id"] for a in flat], [1, 2, 3])
        self.assertEqual({a["category"] for a in flat}, {"Wonders"})
        self.assertEqual(wiki.achievement_where({"quest": {"name": ["A", "B"]}, "commissions": "liyue"}), "Quest: A, B")
        self.assertEqual(wiki.achievement_where({"commissions": "liyue"}), "Liyue commission")

    def test_parse_timeline_and_server_times(self):
        js = """export const eventsData = [
  [
    {
      name: "Adventure's Eve",
      start: '2026-09-23 06:00:00',
      end: '2026-11-03 14:59:00',
      timezoneDependent: true,
      description:
        'Line one.\\nLine two: true',
    },
  ],
  [
    {
      name: 'Abyss',
      start: '2026-10-01 04:00:00',
      end: '2026-10-16 04:00:00',
      showOnHome: false,
      image: 'abyss',
    },
  ],
];
"""
        rows = wiki.parse_js(js)
        self.assertEqual(rows[0][0]["description"], "Line one.\nLine two: true")
        self.assertIs(rows[0][0]["timezoneDependent"], True)
        start, _ = wiki.event_times(rows[0][0], "os_usa")
        self.assertEqual(start.utcoffset().total_seconds(), -5 * 3600)
        start, _ = wiki.event_times(rows[0][0], None)
        self.assertEqual(start.utcoffset().total_seconds(), 8 * 3600)
        events = [(e, *wiki.event_times(e, "os_euro")) for row in rows for e in row]
        cal = widgets.month_calendar(datetime.date(2026, 10, 1), events, None, print)
        oct_5 = cal.controls[2].controls[0]  # second week, Monday
        self.assertEqual(oct_5.tooltip, "Adventure's Eve\nAbyss")  # both events
        self.assertIsNone(oct_5.image)  # neither starts nor ends that day
        self.assertEqual(sum(c.image is not None for w in cal.controls[1:] for c in w.controls), 2)  # Abyss's start + end

    def test_current_banners(self):
        js = """export const banners = {
  characters: [
    {
      name: 'Old',
      start: '2026-09-01 18:00:00',
      end: '2026-09-22 14:59:00',
      featured: ['flins'],
    },
    // {
    //   name: 'Commented out',
    // },
    {
      name: 'Now',
      start: '2026-09-23 06:00:00',
      end: '2026-10-13 17:59:59',
      featured: ['kuki_shinobu'],
      timezoneDependent: true,
    },
  ],
  weapons: [
    {
      name: 'Next',
      start: '2026-10-14 06:00:00',
      end: '2026-11-03 17:59:59',
      featured: ['aqua_simulacra'],
    },
  ],
};
"""
        data = wiki.parse_js(js)
        now = datetime.datetime(2026, 10, 3, tzinfo=datetime.timezone.utc)
        live = wiki.current_banners(data, "os_euro", now)
        self.assertEqual([(pool, b["name"]) for pool, b, *_ in live],
                         [("Character Event Wish", "Now"), ("Weapon Event Wish", "Next")])
        wiki._icons.clear()
        wiki._icons.update({"": None, "Kuki Shinobu": "k.png"})  # skip the DB read
        self.assertEqual(wiki.name_for("kuki_shinobu"), "Kuki Shinobu")
        self.assertEqual(wiki.name_for("new_one"), "New One")
        self.assertTrue(widgets.banner_tile(*live[0]).content.content.controls)
        self.assertTrue(wiki.banner_image({"name": "Ode to the Dawn Breeze", "image": 2})
                        .endswith("/Ode%20to%20the%20Dawn%20Breeze%202.png"))
        self.assertIsNone(wiki.banner_image({"name": "Next"}))
        wiki._icons.clear()

    def test_patches_span_their_banners(self):
        data = {"characters": [
            {"version": "7.1", "start": "2026-10-14 18:00:00", "end": "2026-11-03 14:59:00"},
            {"version": "7.0", "start": "2026-08-12 06:00:00", "end": "2026-09-01 17:59:00", "timezoneDependent": True},
            {"version": "7.1", "start": "2026-09-23 06:00:00", "end": "2026-10-13 17:59:59"},
            {"start": "2020-09-28 10:00:00", "end": "2020-10-18 15:59:00"}]}
        p = wiki.patches(data)
        self.assertEqual([v for v, *_ in p], ["7.0", "7.1"])
        self.assertEqual((p[1][1].day, p[1][2].day), (23, 3))
        cal = widgets.month_calendar(datetime.date(2026, 10, 1), [], datetime.date(2026, 10, 5), print)
        self.assertEqual(len(cal.controls), 6)  # weekday header + 5 weeks (October 2026: Thu 1st .. Sat 31st)

    def test_menu_cache_skips_refetch_when_count_unchanged(self):
        conn = db.connect(":memory:")
        stale = (datetime.date.today() - datetime.timedelta(5)).isoformat()
        db.set_meta(conn, "wiki:x", json.dumps({"date": stale, "data": [1, 2]}))
        fetched = []
        got = wiki._cached(conn, "wiki:x", lambda: fetched.append(1) or [1, 2, 3], unchanged=lambda old: len(old) == 2)
        self.assertEqual((got, fetched), ([1, 2], []))
        self.assertEqual(json.loads(db.get_meta(conn, "wiki:x"))["date"], datetime.date.today().isoformat())

    def test_prefetch_entries_waits_only_after_a_download(self):
        conn, sleeps = db.connect(":memory:"), []
        page = {"name": "Lisa", "icon_url": "i", "desc": "", "modules": [{"name": "Talents", "components": [
            {"component_id": "talent", "data": json.dumps({"list": [{"title": "T", "desc": "d", "icon_url": "t.png"}]})}]}]}
        with mock.patch.object(wiki, "request", return_value={"data": {"page": page}}) as req:
            self.assertEqual(wiki.prefetch_entries(conn, [1], sleeps.append), ["", "t.png"])
            wiki.prefetch_entries(conn, [1], sleeps.append)  # cached this week: no request, no wait
        self.assertEqual((req.call_count, len(sleeps)), (1, 1))

    def test_short_skill_text(self):
        talent = "Channels lightning.\n\nTap/Press\nReleases an orb. On hit, it deals DMG.\n\nHold\nCalls lightning.\n\nLore line."
        self.assertEqual(wiki.short(talent), "Tap/Press\nReleases an orb.\nHold\nCalls lightning.")
        listed = "Holding it has the following effects:\n·DEF +25%.\n·Less interruption.\nMax 15."
        self.assertEqual(wiki.short(listed), "Holding it has the following effects:\n·DEF +25%.\n·Less interruption.")
        self.assertEqual(wiki.short("Deals 1.5% DMG. Then more."), "Deals 1.5% DMG.")

    def test_achievement_ticks_round_trip(self):
        conn = db.connect(":memory:")
        db.set_done(conn, 7, True)
        db.set_done(conn, 7, True)
        db.set_done(conn, 8, True)
        db.set_done(conn, 8, False)
        self.assertEqual(db.done_ids(conn), {7})


class TestHelpers(unittest.TestCase):
    def test_crit_value(self):
        subs = [{"property_type": 20, "value": "3.5%"}, {"property_type": 22, "value": "28.0%"},
                {"property_type": 2, "value": "311"}]
        self.assertAlmostEqual(widgets.crit_value(subs), 35.0)

    def test_clean_rich_text(self):
        self.assertEqual(widgets.clean(r"<color=#FFD780FF>Skill</color>{LINK#N1}Link{/LINK}\nNext"), "SkillLink\nNext")

    def test_pool_stats_entries_carry_id_and_rank(self):
        rows = [{"id": str(i), "rank": 4 if i == 3 else 5 if i == 5 else 3, "name": "X", "item_type": "Character",
                 "time": "2024-01-01 00:00:00"} for i in range(1, 6)]
        s = wish.pool_stats(rows, 90)
        self.assertEqual([(f["id"], f["rank"]) for f in s["four_stars"] + s["five_stars"]], [("3", 4), ("5", 5)])


class TestImageCache(unittest.TestCase):
    def test_downloaded_once_then_served_from_disk(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp,                 mock.patch.object(wiki, "_image_dir", lambda: Path(tmp)),                 mock.patch.object(wiki, "_get", lambda url: calls.append(url) or b"png"):
            url = "https://example.com/a/icon.png"
            self.assertEqual(wiki.image(url), url)  # not cached: Flutter loads the URL
            wiki.cache_images([url, url, None])
            wiki.cache_images([url])
            self.assertEqual(calls, [url])
            self.assertEqual(Path(wiki.image(url)).read_bytes(), b"png")
            self.assertTrue(wiki.image(url).endswith(".png"))

    def test_farming_and_guides(self):
        items = ("export const itemList = {\n  teachings_of_freedom: {\n    id: 'teachings_of_freedom',\n"
                 "    name: 'Teachings of Freedom',\n    day: ['monday', 'thursday'],\n    rarity: 2,\n  },\n"
                 "  tile_of_decarabians_tower: {\n    id: 'tile_of_decarabians_tower',\n"
                 "    name: \"Tile of Decarabian's Tower\",\n    day: ['monday', 'thursday'],\n  },\n};")
        chars = ("export const characters = {\n  amber: {\n    id: 'amber',\n    name: 'Amber',\n    rarity: 4,\n"
                 "    material: {\n      book: [itemList.teachings_of_freedom],\n    },\n  },\n};")
        weapons = ("export const weaponList = {\n  wolfs_gravestone: {\n    name: \"Wolf's Gravestone\",\n    rarity: 5,\n"
                   "    ascension: [{ items: [{ item: itemList.tile_of_decarabians_tower }] }],\n  },\n"
                   "  dull_blade: {\n    name: 'Dull Blade',\n    rarity: 1,\n"
                   "    ascension: [{ items: [{ item: itemList.tile_of_decarabians_tower }] }],\n  },\n};")
        data = wiki.parse_farming(items, chars, weapons)
        self.assertEqual(data, [
            {"name": "Teachings of Freedom", "kind": "talent", "days": [0, 3], "items": [["Amber", 4]]},
            {"name": "Tile of Decarabian's Tower", "kind": "weapon", "days": [0, 3],
             "items": [["Wolf's Gravestone", 5]]}])  # 1★ weapons left out
        utc = datetime.timezone.utc
        monday_noon, tuesday_3am_asia = datetime.datetime(2026, 10, 5, 4, tzinfo=utc), datetime.datetime(2026, 10, 5, 18, tzinfo=utc)
        self.assertEqual(len(wiki.todays_domains(data, "os_asia", monday_noon)), 2)
        self.assertEqual(wiki.farm_day("os_asia", tuesday_3am_asia), 0)  # before the 04:00 reset
        self.assertEqual(wiki.todays_domains(data, "os_asia", monday_noon + datetime.timedelta(days=1)), [])
        self.assertEqual(len(wiki.todays_domains(data, "os_asia", monday_noon + datetime.timedelta(days=6))), 2)

        g = {"builds": {"amber": {"roles": {"SUPPORT": {"weapons": [{"id": "favonius_warbow", "refine": [3]}],
                                                       "artifacts": [["noblesse_oblige"], ["a", "+18%_atk_set"]],
                                                       "note": "Use <b>burst</b>."},
                                           "DPS": {"recommended": True, "weapons": [], "artifacts": []}}}},
             "artifacts": {"noblesse_oblige": "Noblesse Oblige", "a": "A"}}
        support, = [r for r in wiki.guide_roles(g, "Amber") if r["role"] == "SUPPORT"]
        self.assertEqual(wiki.guide_roles(g, "Amber")[0]["role"], "DPS")  # recommended first
        self.assertEqual(support["artifacts"], ["Noblesse Oblige (4)", "A / +18% ATK SET (2+2)"])
        self.assertTrue(support["weapons"][0].endswith(" R3"))
        self.assertEqual(support["note"], "Use burst.")
        self.assertEqual(wiki.guide_roles(g, "Nobody"), [])
        self.assertIn("Amber+genshin", wiki.video_url("Amber"))
        self.assertEqual(wiki.genshintrack_url("Arataki Itto"), "https://genshintrack.com/characters/arataki-itto")
        # Own picks (data/builds.json) win, so no paimon.moe request; everyone else falls back to paimon.moe.
        with mock.patch.object(wiki, "guides", return_value=g) as fetch:
            self.assertEqual(wiki.build_guide(None, "Furina")[0]["role"], "Sub DPS / Buffer")
            fetch.assert_not_called()
            self.assertEqual(wiki.build_guide(None, "Amber")[0]["role"], "DPS")
        keys = {"role", "recommended", "weapons", "artifacts", "main", "subs", "talents"}
        for name, roles in wish.load_data("builds.json")["characters"].items():
            for r in roles:
                self.assertLessEqual(keys, r.keys(), name)
                self.assertTrue(all(a.endswith((" (4)", " (2+2)")) for a in r["artifacts"]), name)


if __name__ == "__main__":
    unittest.main()
