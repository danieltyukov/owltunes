import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hw"))
from hw_bom import check  # noqa: E402


class BomCheckTest(unittest.TestCase):
    def test_matching_fields_pass_and_unassembled_parts_are_skipped(self):
        design = {"part": [{"ref": "R1", "lcsc": "C25744", "mpn": "0402WGF1002TCE"}, {"ref": "TP1", "assembled": False}]}
        comps = {"R1": {"fields": {"LCSC Part #": "C25744", "MPN": "0402WGF1002TCE"}}}
        self.assertEqual(check(design, comps), [])

    def test_wrong_missing_and_malformed_fields_are_reported(self):
        design = {"part": [{"ref": "R1", "lcsc": "C25744", "mpn": "X"}, {"ref": "U1", "lcsc": "15220", "mpn": "Y"}]}
        comps = {"R1": {"fields": {"LCSC Part #": "C25745", "MPN": "X"}}, "U1": {"fields": {}}}
        errors = check(design, comps)
        self.assertIn("R1: field 'LCSC Part #' is 'C25745', design says 'C25744'", errors)
        self.assertIn("U1: design.toml lcsc '15220' is not an LCSC number", errors)
        self.assertIn("U1: field 'MPN' is None, design says 'Y'", errors)


if __name__ == "__main__":
    unittest.main()
