import unittest

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


if __name__ == "__main__":
    unittest.main()
