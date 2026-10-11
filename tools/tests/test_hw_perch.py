"""Perch board: pins and pads line up with the owl, and the dock link matches the main board."""

import pathlib
import sys
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "enclosure"))
import owl_params as P  # noqa: E402

PERCH = ROOT / "hardware" / "perch-dock"
MAIN = ROOT / "hardware" / "owl-mainboard"
PIN_X = {"P1": -P.DOCK_PAD_PITCH, "P2": 0.0, "P3": P.DOCK_PAD_PITCH}
PAD_X = {"PAD1": -P.DOCK_PAD_PITCH, "PAD2": 0.0, "PAD3": P.DOCK_PAD_PITCH}
PIN_NET = {"PAD_DET": "DOCK_ID", "PAD_GND": "GND", "PAD_VBUS": "VBUS_OUT"}
LINK = {"PAD_GND": "GND", "PAD_VBUS": "VBUS_DOCK", "PAD_DET": "DOCK_PAD"}


def parts(path):
    return {p["ref"]: p for p in tomllib.loads((path / "design.toml").read_text())["part"]}


class PerchTest(unittest.TestCase):
    def setUp(self):
        if not (PERCH / "design.toml").exists():
            self.skipTest("perch design.toml not written yet")
        self.perch = parts(PERCH)

    def test_pads_and_pins_follow_the_owl_order(self):
        order = dict(zip((-P.DOCK_PAD_PITCH, 0.0, P.DOCK_PAD_PITCH), P.DOCK_PAD_ORDER))
        for ref, x in PAD_X.items():
            self.assertEqual(self.perch[ref]["pins"]["1"], order[x], ref)
            self.assertEqual(self.perch[ref]["side"], "back", ref)
        for ref, x in PIN_X.items():
            self.assertEqual(self.perch[ref]["pins"]["1"], PIN_NET[order[x]], ref)

    def test_pad_link_matches_the_main_board_dock_connector(self):
        if not (MAIN / "design.toml").exists():
            self.skipTest("main board design.toml not written yet")
        j303 = parts(MAIN)["J303"]["pins"]
        j2 = self.perch["J2"]["pins"]
        for pin in ("1", "2", "3", "4"):
            self.assertEqual(LINK[j2[pin]], j303[pin], pin)

    def test_pin_positions_on_the_board(self):
        try:
            import pcbnew
        except ImportError:
            self.skipTest("needs KiCad's pcbnew module")
        pcb = PERCH / "perch-dock.kicad_pcb"
        board = pcbnew.LoadBoard(str(pcb)) if pcb.exists() else None
        if board is None:
            self.skipTest("perch board not created yet")
        refs = {fp.GetReference(): fp for fp in board.GetFootprints()}
        if "P2" not in refs:
            self.skipTest("perch board not placed yet")
        for group, centre in ((PIN_X, "P2"), (PAD_X, "PAD2")):
            cx = pcbnew.ToMM(refs[centre].GetPosition().x)
            cy = pcbnew.ToMM(refs[centre].GetPosition().y)
            for ref, x in group.items():
                fx = pcbnew.ToMM(refs[ref].GetPosition().x) - cx
                fy = pcbnew.ToMM(refs[ref].GetPosition().y) - cy
                self.assertAlmostEqual(fx, x, places=2, msg=ref)
                self.assertAlmostEqual(fy, 0.0, places=2, msg=ref)


if __name__ == "__main__":
    unittest.main()
