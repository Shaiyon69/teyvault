import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from teyvat import db, gui, wiki, wish

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

    def test_flatten_tiered_achievements(self):
        raw = {"0": {"name": "Wonders", "achievements": [
            {"id": 1, "name": "One", "reward": 5},
            [{"id": 2, "name": "Tier", "reward": 5}, {"id": 3, "name": "Tier", "reward": 10}]]}}
        flat = wiki.flatten_achievements(raw)
        self.assertEqual([a["id"] for a in flat], [1, 2, 3])
        self.assertEqual({a["category"] for a in flat}, {"Wonders"})

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
        chart = gui.timeline_chart(rows, "os_euro")
        self.assertTrue(chart.controls)

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
        self.assertTrue(gui.banner_tile(*live[0]).content.controls)
        wiki._icons.clear()

    def test_menu_cache_skips_refetch_when_count_unchanged(self):
        conn = db.connect(":memory:")
        stale = (datetime.date.today() - datetime.timedelta(5)).isoformat()
        db.set_meta(conn, "wiki:x", json.dumps({"date": stale, "data": [1, 2]}))
        fetched = []
        got = wiki._cached(conn, "wiki:x", lambda: fetched.append(1) or [1, 2, 3], unchanged=lambda old: len(old) == 2)
        self.assertEqual((got, fetched), ([1, 2], []))
        self.assertEqual(json.loads(db.get_meta(conn, "wiki:x"))["date"], datetime.date.today().isoformat())

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
        self.assertAlmostEqual(gui.crit_value(subs), 35.0)

    def test_clean_rich_text(self):
        self.assertEqual(gui.clean(r"<color=#FFD780FF>Skill</color>{LINK#N1}Link{/LINK}\nNext"), "SkillLink\nNext")

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


if __name__ == "__main__":
    unittest.main()
