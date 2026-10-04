import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from check_style import find_banned, should_check  # noqa: E402


class FindBannedTest(unittest.TestCase):
    def test_plain_text_passes(self):
        self.assertEqual(find_banned("A hyphen-separated range: 3-5 mm.\n"), [])

    def test_em_and_en_dash_are_reported_with_position(self):
        self.assertEqual(find_banned("ok\na\u2014b \u2013c\n"), [(2, 2, "\u2014"), (2, 5, "\u2013")])

    def test_emoji_is_reported(self):
        self.assertEqual(find_banned("owl \U0001f989"), [(1, 5, "\U0001f989")])

    def test_accented_and_cjk_text_passes(self):
        self.assertEqual(find_banned("Bj\u00f6rk \u591c\u9593\u98db\u884c"), [])


class ShouldCheckTest(unittest.TestCase):
    def test_licence_and_images_are_skipped(self):
        self.assertFalse(should_check(pathlib.Path("LICENSE-HARDWARE")))
        self.assertFalse(should_check(pathlib.Path("sim/golden/now_playing.png")))
        self.assertTrue(should_check(pathlib.Path("README.md")))


if __name__ == "__main__":
    unittest.main()
