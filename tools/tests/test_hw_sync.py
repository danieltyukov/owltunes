import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HW = pathlib.Path(__file__).resolve().parent.parent / "hw"
sys.path.insert(0, str(HW))
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
            self.assertEqual(fp.IsFlipped(), part.get("side", "front") == "back", f"{ref} side")
            for pad in fp.Pads():
                want = part.get("pins", {}).get(pad.GetNumber())
                if want is not None:
                    self.assertEqual(pad.GetNetname(), want, f"{ref}.{pad.GetNumber()}")

    def test_toolkit_offsets_reach_the_footprints(self):
        # The Fabrication Toolkit reads FT Rotation Offset and FT Position Offset from the
        # footprint, not the symbol; design.toml holds them as rotation_offset and position_offset.
        for name in ("owl-mainboard", "perch-dock"):
            board = pcbnew.LoadBoard(str(ROOT / "hardware" / name / f"{name}.kicad_pcb"))
            parts = load_design(name)["part"]
            for field, key in (("FT Rotation Offset", "rotation_offset"), ("FT Position Offset", "position_offset")):
                want = {p["ref"]: str(p[key]) for p in parts if key in p}
                have = {fp.GetReference(): fp.GetField(field).GetText() for fp in board.GetFootprints() if fp.HasField(field)}
                self.assertEqual(have, want, f"{name} {field}")
                for ref in have:
                    self.assertFalse(board.FindFootprintByReference(ref).GetField(field).IsVisible(), f"{name} {ref}")

    def test_main_board_footprints_match_their_library_copies(self):
        # A library edit (such as the trimmed WROOM-1 antenna keep-out) reaches the board via hw_sync.py.
        board = pcbnew.LoadBoard(str(ROOT / "hardware" / "owl-mainboard" / "owl-mainboard.kicad_pcb"))
        for fp in board.GetFootprints():
            nick, name = fp.GetFPIDAsString().split(":", 1)
            lib_fp = pcbnew.FootprintLoad(str(hw_sync.library(nick)), name)
            self.assertEqual(hw_sync.signature(fp), hw_sync.signature(lib_fp), fp.GetReference())


@unittest.skipIf(pcbnew is None, "needs KiCad's pcbnew module")
class SyncRemovesInAFreshInterpreterTest(unittest.TestCase):
    def test_removed_and_replaced_footprints_leave_the_bindings_working(self):
        # Board.Remove leaves a removed footprint to its Python wrapper, and once the wrapper is
        # freed pcbnew returns untyped objects for every board. The fault shows in a fresh
        # interpreter, so sync runs in one (with the schematic read stubbed) and the same
        # interpreter then loads the result.
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp) / "hardware" / "b"
            folder.mkdir(parents=True)
            path = folder / "b.kicad_pcb"
            board = pcbnew.BOARD()
            # The nets exist already, as on a real board: a NETINFO_ITEM made after the removal
            # happens to hide the fault.
            nets = [pcbnew.NETINFO_ITEM(board, name) for name in ("N1", "N2")]
            for net in nets:
                board.Add(net)
            for ref, x in (("R1", 110), ("R2", 120)):
                fp = pcbnew.FootprintLoad("/usr/share/kicad/footprints/Resistor_SMD.pretty", "R_0402_1005Metric")
                fp.SetFPIDAsString("Resistor_SMD:R_0402_1005Metric")
                fp.SetReference(ref)
                fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(100)))
                fp.SetLocked(True)
                board.Add(fp)
                for pad, net in zip(fp.Pads(), nets):
                    pad.SetNet(net)
            pcbnew.SaveBoard(str(path), board)
            # R1 changes footprint (replaced in place), R2 leaves the schematic, R3 is new.
            comps = {ref: {"value": "1k", "footprint": f"Resistor_SMD:{name}", "fields": {}, "props": {},
                           "path": f"/00000000-0000-0000-0000-00000000000{i}", "sheetname": "", "sheetfile": ""}
                     for i, (ref, name) in enumerate((("R1", "R_0603_1608Metric"), ("R3", "R_0402_1005Metric")))}
            pins = {(ref, pin): f"N{pin}" for ref in comps for pin in ("1", "2")}
            script = "\n".join([
                "import gc, json, pathlib, sys",
                f"sys.path.insert(0, {str(HW)!r})",
                "import pcbnew, hw_sync",
                f"hw_sync.ROOT = pathlib.Path({tmp!r})",
                f"comps = {comps!r}",
                f"pins = {pins!r}",
                "hw_sync.read = lambda name: (comps, pins)",
                "rc = hw_sync.sync('b')",
                "gc.collect()",
                f"board = pcbnew.LoadBoard({str(path)!r})",
                "fps = {f.GetReference(): [f.GetFPIDAsString(), round(pcbnew.ToMM(f.GetPosition().x), 3), f.IsLocked()]",
                "       for f in board.GetFootprints()}",
                "print(json.dumps(fps))",
                "sys.exit(rc)",
            ])
            run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr[-1500:])
            fps = json.loads(run.stdout.strip().splitlines()[-1])
            self.assertEqual(sorted(fps), ["R1", "R3"])
            self.assertEqual(fps["R1"], ["Resistor_SMD:R_0603_1608Metric", 110.0, True])
            self.assertEqual(fps["R3"][0], "Resistor_SMD:R_0402_1005Metric")


if __name__ == "__main__":
    unittest.main()
