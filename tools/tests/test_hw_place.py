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
    import hw_place


@unittest.skipIf(pcbnew is None, "needs KiCad's pcbnew module")
class MarkJ101Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.tmp.name) / "b.kicad_pcb"
        board = pcbnew.BOARD()
        fp = pcbnew.FootprintLoad("/usr/share/kicad/footprints/Resistor_SMD.pretty", "R_0402_1005Metric")
        fp.SetReference("R1")
        board.Add(fp)
        hw_place.mark_j101(board)
        # A mark the 3-pin J101 had and the 2-pin one does not.
        old = pcbnew.PCB_TEXT(board)
        old.SetText("NTC")
        old.SetLayer(pcbnew.B_SilkS)
        old.SetTextPos(pcbnew.VECTOR2I(pcbnew.FromMM(128.7), pcbnew.FromMM(82.0)))
        board.Add(old)
        pcbnew.SaveBoard(str(self.path), board)

    def tearDown(self):
        self.tmp.cleanup()

    def run_fresh(self, lines):
        """Run lines in a fresh interpreter and return the JSON its last output line holds."""
        script = "\n".join([
            "import gc, json, sys",
            f"sys.path.insert(0, {str(HW)!r})",
            "import pcbnew, hw_place",
            f"board = pcbnew.LoadBoard({str(self.path)!r})",
            *lines,
            "silk = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.B_SilkS]",
            "texts = sorted(d.GetText() for d in silk if isinstance(d, pcbnew.PCB_TEXT))",
            "dots = sum(1 for d in silk if isinstance(d, pcbnew.PCB_SHAPE))",
            "print(json.dumps([texts, dots, [f.GetReference() for f in board.GetFootprints()]]))",
        ])
        run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-1500:])
        return json.loads(run.stdout.strip().splitlines()[-1])

    def test_clearing_the_marks_leaves_the_bindings_working(self):
        # Board.Remove leaves a removed drawing to its Python wrapper, and once the wrapper is
        # freed pcbnew returns untyped objects for every board. The fault shows in a fresh
        # interpreter, so the run happens in one.
        texts, dots, refs = self.run_fresh(["hw_place.clear_j101_marks(board)", "gc.collect()"])
        self.assertEqual((texts, dots, refs), ([], 0, ["R1"]))

    def test_clearing_keeps_other_silkscreen_beside_j101(self):
        # Only the marks hw_place draws go: the same texts just outside J101_MARK_AREA, another
        # text and another dot inside it, all stay. The 3-pin J101's pin 1 dot (y 16) goes.
        board = pcbnew.LoadBoard(str(self.path))
        x0, y0, x1, y1 = hw_place.J101_MARK_AREA
        for text, x, y in (("+", x0 - 0.05, 17.0), ("-", x1 + 0.05, 19.0), ("fab", 28.0, 20.5)):
            t = pcbnew.PCB_TEXT(board)
            t.SetText(text)
            t.SetLayer(pcbnew.B_SilkS)
            t.SetTextPos(pcbnew.VECTOR2I(pcbnew.FromMM(100 + x), pcbnew.FromMM(100 - y)))
            board.Add(t)
        for x, y in ((28.0, 15.5), (27.35, 16.0)):
            dot = pcbnew.PCB_SHAPE(board)
            dot.SetShape(pcbnew.SHAPE_T_CIRCLE)
            dot.SetLayer(pcbnew.B_SilkS)
            dot.SetFilled(True)
            dot.SetCenter(pcbnew.VECTOR2I(pcbnew.FromMM(100 + x), pcbnew.FromMM(100 - y)))
            dot.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(100 + x + 0.2), pcbnew.FromMM(100 - y)))
            board.Add(dot)
        pcbnew.SaveBoard(str(self.path), board)
        texts, dots, refs = self.run_fresh(["hw_place.clear_j101_marks(board)", "gc.collect()"])
        self.assertEqual((texts, dots, refs), (["+", "-", "fab"], 1, ["R1"]))

    def test_rerun_replaces_the_marks(self):
        texts, dots, refs = self.run_fresh([
            "hw_place.mark_j101(board)",
            f"pcbnew.SaveBoard({str(self.path)!r}, board)",
            "del board",
            "gc.collect()",
            f"board = pcbnew.LoadBoard({str(self.path)!r})",
        ])
        self.assertEqual(texts, sorted(m[0] for m in hw_place.J101_MARKS))
        self.assertEqual(dots, 1)
        self.assertEqual(refs, ["R1"])


@unittest.skipIf(pcbnew is None, "needs KiCad's pcbnew module")
class PlaceReferencesTest(unittest.TestCase):
    """R1's reference cannot go above or below its pads (too close to them), so its first free
    spot is left of the part, at KiCad (146.8 to 148.6, 149.3 to 150.7). Something on the
    silkscreen there must push it elsewhere, without overlapping."""

    def board_with_r1(self):
        board = pcbnew.BOARD()
        for a, b in (((140, 140), (160, 140)), ((160, 140), (160, 160)), ((160, 160), (140, 160)),
                     ((140, 160), (140, 140))):
            edge = pcbnew.PCB_SHAPE(board)
            edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
            edge.SetLayer(pcbnew.Edge_Cuts)
            edge.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]), pcbnew.FromMM(a[1])))
            edge.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(b[0]), pcbnew.FromMM(b[1])))
            board.Add(edge)
        r1 = pcbnew.FootprintLoad("/usr/share/kicad/footprints/Resistor_SMD.pretty", "R_0402_1005Metric")
        r1.SetReference("R1")
        r1.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(150), pcbnew.FromMM(150)))
        board.Add(r1)
        return board, r1

    def assert_clear(self, board, r1, others):
        self.assertTrue(others)
        self.assertEqual(hw_place.place_references(board), [])
        ref = hw_place.box(r1.Reference())
        for other in others:
            self.assertFalse(hw_place.hits(ref, other, 0.0), (ref, other))

    def test_references_keep_clear_of_board_silkscreen(self):
        board, r1 = self.board_with_r1()
        text = pcbnew.PCB_TEXT(board)  # a hw_silk.py mark
        text.SetText("XX")
        text.SetLayer(pcbnew.F_SilkS)
        text.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
        text.SetTextPos(pcbnew.VECTOR2I(pcbnew.FromMM(147.7), pcbnew.FromMM(150)))
        board.Add(text)
        self.assert_clear(board, r1, [hw_place.box(text)])

    def test_references_keep_clear_of_other_footprints_silkscreen(self):
        board, r1 = self.board_with_r1()
        r2 = pcbnew.FOOTPRINT(board)  # a part well below R1 whose silkscreen outline runs up past it
        r2.SetReference("R2")
        pad = pcbnew.PAD(r2)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetLayerSet(pad.SMDMask())
        pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.5), pcbnew.FromMM(0.5)))
        pad.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(147.7), pcbnew.FromMM(156)))
        r2.Add(pad)
        line = pcbnew.PCB_SHAPE(r2)
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetLayer(pcbnew.F_SilkS)
        line.SetWidth(pcbnew.FromMM(0.12))
        line.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(147.7), pcbnew.FromMM(148.5)))
        line.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(147.7), pcbnew.FromMM(155)))
        r2.Add(line)
        board.Add(r2)
        self.assert_clear(board, r1, [hw_place.box(g) for g in r2.GraphicalItems() if g.GetLayer() == pcbnew.F_SilkS])

if __name__ == "__main__":
    unittest.main()
