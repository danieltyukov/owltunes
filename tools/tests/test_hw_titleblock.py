import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hw"))
from hw_titleblock import apply, check_text  # noqa: E402

SCH = '(kicad_sch\n\t(version 1)\n\t(paper "A4")\n\t(lib_symbols)\n)\n'
D = "2026-01-02"
PCB = '(kicad_pcb\n\t(paper "A4")\n\t(title_block\n\t\t(title "x")\n\t\t(date "2026-01-01")\n\t)\n\t(layers)\n)\n'


class TitleBlockTest(unittest.TestCase):
    def test_missing_block_is_reported_then_added(self):
        self.assertEqual(len(check_text(SCH, "T", D)), 5)
        self.assertEqual(check_text(apply(SCH, "T", D), "T", D), [])

    def test_existing_block_is_replaced_not_duplicated(self):
        out = apply(PCB, "T", D)
        self.assertEqual(out.count("(title_block"), 1)
        self.assertEqual(check_text(out, "T", D), [])
        self.assertEqual(apply(out, "T", D), out)

    def test_wrong_title_is_reported(self):
        self.assertEqual(check_text(apply(SCH, "T", D), "U", D), ["title block title is 'T', expected 'U'"])


if __name__ == "__main__":
    unittest.main()
