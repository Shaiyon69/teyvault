import unittest

from teyvat import gui


class TestMetaTiers(unittest.TestCase):
    def test_data_uses_known_tiers_and_roles(self):
        for name, ratings in gui.PRYDWEN["characters"].items():
            for tier, role in ratings:
                self.assertIn(tier, gui.TIER_COLORS, name)
                self.assertIn(role, ("On-field DPS", "Off-field DPS", "Support"), name)

    def test_traveler_matched_by_element(self):
        self.assertTrue(gui.meta_ratings({"name": "Traveler", "element": "Anemo"}))
        self.assertEqual(gui.meta_ratings({"name": "Nobody", "element": "Pyro"}), [])


if __name__ == "__main__":
    unittest.main()
