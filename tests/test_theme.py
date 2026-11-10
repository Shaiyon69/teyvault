import tempfile
import unittest
from pathlib import Path

from teyvat.gui.theme import gtk_colors


class TestGtkColors(unittest.TestCase):
    def test_imports_and_references(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "gtk.css").write_text('@import url("gen.css");\n@define-color accent_color #adc6ff;\n')
            Path(d, "gen.css").write_text("@define-color window_bg_color #121212;\n"
                                          "@define-color view_bg_color @window_bg_color;\n"
                                          "@define-color shade alpha(black, 0.3);\n")
            self.assertEqual(gtk_colors(Path(d, "gtk.css")), {"accent_color": "#adc6ff", "window_bg_color": "#121212",
                                                              "view_bg_color": "#121212"})
            self.assertEqual(gtk_colors(Path(d, "missing.css")), {})


if __name__ == "__main__":
    unittest.main()
