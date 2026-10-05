import tomllib
import unittest
from pathlib import Path

import teyvat
from teyvat.gui import theme, widgets


class TestMetaTiers(unittest.TestCase):
    def test_data_uses_known_tiers_and_roles(self):
        for name, ratings in theme.PRYDWEN["characters"].items():
            for tier, role in ratings:
                self.assertIn(tier, theme.TIER_COLORS, name)
                self.assertIn(role, ("On-field DPS", "Off-field DPS", "Support"), name)

    def test_traveler_matched_by_element(self):
        self.assertTrue(widgets.meta_ratings({"name": "Traveler", "element": "Anemo"}))
        self.assertEqual(widgets.meta_ratings({"name": "Nobody", "element": "Pyro"}), [])


class TestVersion(unittest.TestCase):
    def test_about_version_matches_pyproject(self):
        pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(teyvat.__version__, pyproject["project"]["version"])


if __name__ == "__main__":
    unittest.main()


class TestThemeSwitch(unittest.TestCase):
    def test_palette_and_style_reset(self):
        """A live theme change rebuilds the UI, so light -> dark and glass -> clean must fully undo."""
        dark = theme.accents()
        theme.use_palette(True)
        self.assertNotEqual(theme.accents(), dark)
        theme.use_palette(False)
        self.assertEqual(theme.accents(), dark)
        self.assertEqual(theme.ELEMENT_COLORS["Pyro"], "#F08A5D")
        theme.use_style("glass", False, False)
        theme.use_style("clean", False, False)
        self.assertIsNone(theme.STYLE["border"])
        self.assertIsNone(theme.STYLE["page_bg"])
