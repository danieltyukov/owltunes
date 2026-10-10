import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hw"))
from hw_kicad import describe, drc_violations, erc_violations  # noqa: E402

VIOLATION = {
    "type": "pin_not_connected",
    "description": "Pin not connected",
    "severity": "error",
    "items": [{"description": "Pin 1", "pos": {"x": 1.5, "y": 2.5}}],
}


class KicadReportTest(unittest.TestCase):
    def test_erc_counts_every_sheet_and_names_the_place(self):
        data = {"sheets": [{"path": "/", "violations": [VIOLATION]},
                           {"path": "/power/", "violations": [VIOLATION, dict(VIOLATION, severity="warning")]},
                           {"path": "/mcu_usb/", "violations": []}]}
        lines = erc_violations(data)
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "error pin_not_connected: Pin not connected at (1.5, 2.5) mm [/]")
        self.assertTrue(lines[2].startswith("warning pin_not_connected") and lines[2].endswith("[/power/]"))

    def test_clean_reports_count_zero(self):
        self.assertEqual(erc_violations({"sheets": [{"path": "/", "violations": []}]}), [])
        self.assertEqual(drc_violations({"violations": [], "unconnected_items": [], "schematic_parity": []}), ([], [], []))

    def test_drc_counts_violations_unconnected_and_parity_separately(self):
        data = {"violations": [VIOLATION, VIOLATION], "unconnected_items": [VIOLATION],
                "schematic_parity": [VIOLATION, VIOLATION, VIOLATION]}
        v, u, p = drc_violations(data)
        self.assertEqual((len(v), len(u), len(p)), (2, 1, 3))

    def test_describe_tolerates_missing_items(self):
        self.assertEqual(describe({"type": "t", "description": "d", "severity": "error"}), "error t: d")


if __name__ == "__main__":
    unittest.main()
