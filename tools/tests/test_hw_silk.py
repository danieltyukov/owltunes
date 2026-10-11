import contextlib
import io
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
    import hw_silk


def mm(v):
    return round(pcbnew.ToMM(v), 4)


@unittest.skipIf(pcbnew is None, "needs KiCad's pcbnew module")
class SilkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        (root / "hardware" / "b").mkdir(parents=True)
        self.path = root / "hardware" / "b" / "b.kicad_pcb"
        board = pcbnew.BOARD()
        other = pcbnew.PCB_TEXT(board)  # silkscreen that is not the tool's must stay
        other.SetText("keep")
        other.SetLayer(pcbnew.B_SilkS)
        other.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
        other.SetTextThickness(pcbnew.FromMM(0.15))
        board.Add(other)
        pcbnew.SaveBoard(str(self.path), board)
        self.saved = hw_silk.ROOT, dict(hw_silk.MARKS)
        hw_silk.ROOT = root

    def tearDown(self):
        hw_silk.ROOT = self.saved[0]
        hw_silk.MARKS.clear()
        hw_silk.MARKS.update(self.saved[1])
        self.tmp.cleanup()

    def silk(self, marks):
        hw_silk.MARKS["b"] = marks
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(hw_silk.silk("b"), 0)
        return pcbnew.LoadBoard(str(self.path))

    def items(self, board):
        """Every silkscreen drawing as (kind, layer, text, x, y, height or radius, stroke, mirrored,
        locked, group name), in owl mm."""
        out = []
        for d in board.GetDrawings():
            group = d.GetParentGroup()
            name = group.GetName() if group else None
            if isinstance(d, pcbnew.PCB_TEXT):
                p = d.GetTextPos()
                out.append(("text", board.GetLayerName(d.GetLayer()), d.GetText(), round(mm(p.x) - 100, 4), round(100 - mm(p.y), 4),
                            mm(d.GetTextHeight()), mm(d.GetTextThickness()), d.IsMirrored(), d.IsLocked(), name))
            else:
                c = d.GetCenter()
                out.append(("dot", board.GetLayerName(d.GetLayer()), "", round(mm(c.x) - 100, 4), round(100 - mm(c.y), 4),
                            mm(d.GetRadius()), mm(d.GetWidth()), d.IsSolidFill(), d.IsLocked(), name))
        return sorted(out, key=str)

    def test_marks_are_drawn_mirrored_on_the_back_and_replaced(self):
        self.silk([("OLD", "B", 1.0, 1.0, 1.0)])
        board = self.silk([("Tyukov Inc", "B", 2.0, -3.0, 1.0), ("31", "F", -4.5, 14.5, 0.8),
                           ("dot", "B", 10.0, 35.9, 0.2)])
        self.assertEqual(self.items(board), sorted([
            ("text", "B.Silkscreen", "Tyukov Inc", 2.0, -3.0, 1.0, 0.15, True, True, "hw_silk"),
            ("text", "F.Silkscreen", "31", -4.5, 14.5, 0.8, 0.15, False, True, "hw_silk"),
            ("dot", "B.Silkscreen", "", 10.0, 35.9, 0.2, 0.1, True, True, "hw_silk"),
            ("text", "B.Silkscreen", "keep", -100.0, 100.0, 1.0, 0.15, False, False, None),
        ], key=str))

    def test_rerun_in_a_fresh_interpreter(self):
        # Board.Remove leaves a removed item to its Python wrapper, and once the wrapper is freed
        # the board's lists stop being iterable; the fault only shows in a fresh interpreter.
        self.silk([("A", "B", 0.0, 0.0, 1.0), ("dot", "F", 1.0, 1.0, 0.2)])
        script = "\n".join([
            "import pathlib, sys",
            f"sys.path.insert(0, {str(HW)!r})",
            "import hw_silk",
            f"hw_silk.ROOT = pathlib.Path({self.tmp.name!r})",
            "hw_silk.MARKS['b'] = [('B', 'F', 0.0, 0.0, 0.8)]",
            "sys.exit(hw_silk.silk('b'))",
        ])
        run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-1500:])
        texts = [t[2] for t in self.items(pcbnew.LoadBoard(str(self.path))) if t[0] == "text"]
        self.assertEqual(sorted(texts), ["B", "keep"])

    def test_every_board_mark_meets_the_jlc_minimums(self):
        # JLC: text 0.8 mm high or more with a 0.15 mm stroke; the owner mark 1.0 mm (11 October
        # owner request); the order-number mark is on the back.
        for board, marks in self.saved[1].items():
            for what, side, x, y, size in marks:
                self.assertIn(side, ("F", "B"))
                if what == "dot":
                    self.assertGreaterEqual(size, 0.15, board)
                else:
                    self.assertGreaterEqual(size, 1.0 if what == "Tyukov Inc" else 0.8, (board, what))
        self.assertGreaterEqual(hw_silk.STROKE, 0.15)
        for board in ("owl-mainboard", "perch-dock"):
            self.assertIn("Tyukov Inc", [m[0] for m in self.saved[1][board]], board)
        self.assertIn(("JLCJLCJLCJLC", "B"), [(m[0], m[1]) for m in self.saved[1]["owl-mainboard"]])


if __name__ == "__main__":
    unittest.main()
