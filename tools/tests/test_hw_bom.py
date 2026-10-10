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

    def test_missing_or_empty_mpn_fails_even_when_the_field_is_empty_too(self):
        design = {"part": [{"ref": "R1", "lcsc": "C25744"}, {"ref": "R2", "lcsc": "C25744", "mpn": ""}]}
        comps = {"R1": {"fields": {"LCSC Part #": "C25744"}}, "R2": {"fields": {"LCSC Part #": "C25744", "MPN": ""}}}
        errors = check(design, comps)
        self.assertIn("R1: design.toml has no mpn", errors)
        self.assertIn("R2: design.toml has no mpn", errors)
        self.assertIn("R2: field 'MPN' is '', design says ''", errors)

    def test_sheet_filter_skips_other_sheets(self):
        design = {"part": [{"ref": "R1", "sheet": "power", "lcsc": "C1", "mpn": "A"},
                           {"ref": "R2", "sheet": "periph", "lcsc": "bad", "mpn": ""}]}
        comps = {"R1": {"fields": {"LCSC Part #": "C1", "MPN": "A"}}}
        self.assertEqual(check(design, comps, {"power"}), [])
        self.assertEqual(len(check(design, comps)), 3)


if __name__ == "__main__":
    unittest.main()
