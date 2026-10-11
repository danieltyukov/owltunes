import copy
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hw"))
try:
    import pcbnew  # KiCad's module; CI runs in the KiCad container
except ImportError:
    pcbnew = None
if pcbnew is not None:
    import hw_contract

CONTRACT = {
    "outline": [
        {"kind": "line", "start": [90.0, 90.0], "end": [110.0, 90.0]},
        {"kind": "line", "start": [110.0, 90.0], "end": [110.0, 110.0]},
        {"kind": "arc", "start": [110.0, 110.0], "mid": [100.0, 114.0], "end": [90.0, 110.0]},
        {"kind": "line", "start": [90.0, 110.0], "end": [90.0, 90.0]},
    ],
    "placements": [{"ref": "U1", "kicad_x": 95.0, "kicad_y": 100.0, "rot": 90.0, "side": "back",
                    "w": 3.0, "h": 3.0, "cu": 0.0, "cv": 0.0, "knob": []}],
    "mount_holes": [{"ref": "H1", "x": 105.0, "y": 95.0, "d": 2.2}],
    "keepouts": [
        {"kind": "circle", "name": "H1 cover boss", "ref": "H1", "side": "back", "x": 105.0, "y": 95.0, "r": 3.0},
        {"kind": "annulus", "name": "ring", "side": "front", "x": 100.0, "y": 100.0, "r_in": 3.5, "r_out": 5.0},
    ],
    "battery_zone": {"kicad": [97.0, 97.0, 103.0, 103.0], "max_back_height": 1.2},
    "sensor_keepout_mm": 15.0,
}
DESIGN = """
[[part]]
ref = "U1"
height = 1.45
[[part]]
ref = "H1"
height = 0.0
[[part]]
ref = "C1"
height = 3.0
"""


@unittest.skipIf(pcbnew is None, "needs KiCad's pcbnew module")
class ContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.folder = root / "hardware" / "b"
        (self.folder / "mech").mkdir(parents=True)
        self.write_contract(CONTRACT)
        (self.folder / "design.toml").write_text(DESIGN)
        board = pcbnew.BOARD()
        for ref in ("U1", "H1", "C1"):
            fp = pcbnew.FootprintLoad("/usr/share/kicad/footprints/Package_TO_SOT_SMD.pretty", "SOT-23-6")
            fp.SetFPIDAsString("Package_TO_SOT_SMD:SOT-23-6")
            fp.SetReference(ref)
            board.Add(fp)
        pcbnew.SaveBoard(str(self.folder / "b.kicad_pcb"), board)
        self.saved_roots = hw_contract.ROOT, sys.modules["hw_netlist"].ROOT
        hw_contract.ROOT = root
        sys.modules["hw_netlist"].ROOT = root

    def tearDown(self):
        hw_contract.ROOT, sys.modules["hw_netlist"].ROOT = self.saved_roots
        self.tmp.cleanup()

    def write_contract(self, contract):
        (self.folder / "mech" / "contract.json").write_text(json.dumps(contract))

    def board(self):
        return pcbnew.LoadBoard(str(self.folder / "b.kicad_pcb"))

    def move(self, ref, x, y, back):
        board = self.board()
        fp = board.FindFootprintByReference(ref)
        if fp.IsFlipped() != back:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        pcbnew.SaveBoard(str(self.folder / "b.kicad_pcb"), board)

    def test_apply_then_check_passes(self):
        self.assertEqual(hw_contract.apply("b"), 0)
        self.assertEqual(hw_contract.check("b"), 0)
        u1 = self.board().FindFootprintByReference("U1")
        self.assertTrue(u1.IsFlipped())
        self.assertTrue(u1.IsLocked())

    def test_apply_twice_keeps_one_outline(self):
        hw_contract.apply("b")
        self.assertEqual(hw_contract.apply("b"), 0)
        self.assertEqual(hw_contract.check("b"), 0)

    def test_moved_part_and_tall_part_under_the_battery_fail(self):
        hw_contract.apply("b")
        board = self.board()
        board.FindFootprintByReference("U1").SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(96), pcbnew.FromMM(100)))
        c1 = board.FindFootprintByReference("C1")
        c1.Flip(c1.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        c1.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100), pcbnew.FromMM(100)))
        pcbnew.SaveBoard(str(self.folder / "b.kicad_pcb"), board)
        self.assertEqual(hw_contract.check("b"), 1)

    def test_part_on_a_cover_boss_fails_only_on_its_side(self):
        hw_contract.apply("b")
        self.move("C1", 106.5, 95.0, back=False)
        self.assertEqual(hw_contract.check("b"), 0)
        self.move("C1", 106.5, 95.0, back=True)
        self.assertEqual(hw_contract.check("b"), 1)

    def test_front_part_on_the_ring_annulus_fails(self):
        hw_contract.apply("b")
        self.move("C1", 100.0, 100.0, back=False)
        self.assertEqual(hw_contract.check("b"), 0)
        self.move("C1", 100.0, 104.5, back=False)
        self.assertEqual(hw_contract.check("b"), 1)

    def test_a_keepout_spares_the_part_it_names(self):
        strip = copy.deepcopy(CONTRACT)
        strip["keepouts"].append({"kind": "polygon", "name": "U1 strip", "ref": "U1", "side": "back",
                                  "points": [[93.0, 98.0], [97.0, 98.0], [97.0, 102.0], [93.0, 102.0]]})
        self.write_contract(strip)
        hw_contract.apply("b")
        self.assertEqual(hw_contract.check("b"), 0)
        self.move("C1", 95.0, 92.0, back=True)
        self.assertEqual(hw_contract.check("b"), 0)
        self.move("C1", 94.0, 99.5, back=True)  # beside U1, clear of the battery zone
        self.assertEqual(hw_contract.check("b"), 1)

    def test_body_larger_than_its_contract_box_fails(self):
        small = copy.deepcopy(CONTRACT)
        small["placements"][0]["h"] = 2.0  # SOT-23-6 body is 2.9 long along v
        self.write_contract(small)
        hw_contract.apply("b")
        self.assertEqual(hw_contract.check("b"), 1)


if __name__ == "__main__":
    unittest.main()
