import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hw"))
try:
    import pcbnew  # KiCad's module; CI runs in the KiCad container
except ImportError:
    pcbnew = None
if pcbnew is not None:
    import hw_sync
    from hw_netlist import ROOT, load_design


@unittest.skipIf(pcbnew is None, "needs KiCad's pcbnew module")
class SyncTest(unittest.TestCase):
    def test_parse_reads_nested_lists_and_quoted_strings(self):
        tree = hw_sync.parse('(export (comp (ref "R1") (value "4.7k \\"x\\"")) (nets (net (name "GND"))))')
        comp = hw_sync.child(tree, "comp")
        self.assertEqual(hw_sync.value(comp, "ref"), "R1")
        self.assertEqual(hw_sync.value(comp, "value"), '4.7k "x"')
        self.assertEqual([hw_sync.value(n, "name") for n in hw_sync.children(hw_sync.child(tree, "nets"), "net")], ["GND"])

    def test_main_board_footprints_sides_and_pad_nets_follow_the_design(self):
        board = pcbnew.LoadBoard(str(ROOT / "hardware" / "owl-mainboard" / "owl-mainboard.kicad_pcb"))
        design = {p["ref"]: p for p in load_design("owl-mainboard")["part"]}
        fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
        self.assertEqual(set(fps), set(design))
        for ref, part in design.items():
            fp = fps[ref]
            self.assertEqual(fp.GetFPIDAsString(), part["footprint"], ref)
            if not part["footprint"].startswith("MountingHole:"):  # a bare hole has no side
                self.assertEqual(fp.IsFlipped(), part.get("side", "front") == "back", f"{ref} side")
            for pad in fp.Pads():
                want = part.get("pins", {}).get(pad.GetNumber())
                if want is not None:
                    self.assertEqual(pad.GetNetname(), want, f"{ref}.{pad.GetNumber()}")


if __name__ == "__main__":
    unittest.main()
