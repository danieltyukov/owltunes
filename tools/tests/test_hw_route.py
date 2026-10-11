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
    import hw_route


def mm(v):
    return round(pcbnew.ToMM(v), 4)


@unittest.skipIf(pcbnew is None, "needs KiCad's pcbnew module")
class RouteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        folder = root / "hardware" / "b"
        folder.mkdir(parents=True)
        self.path = folder / "b.kicad_pcb"
        board = pcbnew.BOARD()
        # A board keeps only the nets something uses, so a resistor far away carries N1 and N2.
        fp = pcbnew.FootprintLoad("/usr/share/kicad/footprints/Resistor_SMD.pretty", "R_0402_1005Metric")
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(150), pcbnew.FromMM(150)))
        board.Add(fp)
        for pad, name in zip(fp.Pads(), ("N1", "N2")):
            net = pcbnew.NETINFO_ITEM(board, name)
            board.Add(net)
            pad.SetNet(net)
        pcbnew.SaveBoard(str(self.path), board)
        self.saved = hw_route.ROOT, hw_route.GROUPS
        hw_route.ROOT = root

    def tearDown(self):
        hw_route.ROOT, hw_route.GROUPS = self.saved
        self.tmp.cleanup()

    def route(self, groups, *names):
        hw_route.GROUPS = groups
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(hw_route.route("b", list(names)), 0)
        return pcbnew.LoadBoard(str(self.path))

    def copper(self, board):
        """Every track and via as (class, net, start x, start y, end x, end y), in KiCad mm."""
        return sorted((t.GetClass(), t.GetNetname(), mm(t.GetStart().x), mm(t.GetStart().y),
                       mm(t.GetEnd().x), mm(t.GetEnd().y)) for t in board.GetTracks())

    def add_untagged_track(self, net, start, end):
        board = pcbnew.LoadBoard(str(self.path))
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(hw_route.pt(start))
        t.SetEnd(hw_route.pt(end))
        t.SetWidth(pcbnew.FromMM(0.2))
        t.SetNet(board.FindNet(net))
        board.Add(t)
        pcbnew.SaveBoard(str(self.path), board)

    def test_rerun_with_new_coordinates_leaves_no_old_copper(self):
        self.route({"g": [("N1", 0.2, [(0, 0), (1, 0)]), ("N1", "via", [(1, 0)])]}, "g")
        board = self.route({"g": [("N1", 0.2, [(0, 0), (2, 0), (2, 1)]), ("N1", "via", [(2, 1)])]}, "g")
        self.assertEqual(self.copper(board), [
            ("PCB_TRACK", "N1", 100.0, 100.0, 102.0, 100.0),
            ("PCB_TRACK", "N1", 102.0, 100.0, 102.0, 99.0),
            ("PCB_VIA", "N1", 102.0, 99.0, 102.0, 99.0),
        ])
        self.assertTrue(all(t.IsLocked() for t in board.GetTracks()))
        groups = [g for g in board.Groups() if g.GetName() == "hw_route g"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(list(groups[0].GetItems())), 3)

    def test_untagged_copper_at_the_group_coordinates_is_replaced(self):
        # Copper drawn before the tagging (or re-imported from a Specctra session) has no group.
        self.add_untagged_track("N1", (0, 0), (1, 0))
        board = self.route({"g": [("N1", 0.2, [(1, 0), (0, 0)])]}, "g")
        self.assertEqual(self.copper(board), [("PCB_TRACK", "N1", 101.0, 100.0, 100.0, 100.0)])
        self.assertIsNotNone(board.GetTracks()[0].GetParentGroup())

    def test_other_groups_and_other_copper_stay(self):
        self.add_untagged_track("N2", (5, 5), (6, 5))
        groups = {"a": [("N1", 0.2, [(0, 0), (1, 0)])], "b": [("N2", 0.2, [(0, 1), (1, 1)], "F")]}
        self.route(groups, "a", "b")
        board = self.route(dict(groups, a=[("N1", 0.2, [(0, 0), (0, -1)])]), "a")
        self.assertEqual(self.copper(board), [
            ("PCB_TRACK", "N1", 100.0, 100.0, 100.0, 101.0),
            ("PCB_TRACK", "N2", 100.0, 99.0, 101.0, 99.0),
            ("PCB_TRACK", "N2", 105.0, 95.0, 106.0, 95.0),
        ])
        layer = {t.GetNetname(): t.GetLayer() for t in board.GetTracks() if t.GetParentGroup() is not None}
        self.assertEqual(layer, {"N1": pcbnew.B_Cu, "N2": pcbnew.F_Cu})

    def test_rerun_in_a_fresh_interpreter(self):
        # Board.Remove leaves a removed item to its Python wrapper, and once the wrapper is freed
        # the board's track list stops being iterable. The fault shows in a fresh interpreter but
        # not in this test process, so the re-run happens in a fresh interpreter.
        self.route({"g": [("N1", 0.2, [(0, 0), (1, 0), (1, 1)]), ("N1", "via", [(1, 1)])]}, "g")
        script = "\n".join([
            "import pathlib, sys",
            f"sys.path.insert(0, {str(HW)!r})",
            "import hw_route",
            f"hw_route.ROOT = pathlib.Path({self.tmp.name!r})",
            "hw_route.GROUPS = {'g': [('N1', 0.2, [(0, 0), (2, 0)])]}",
            "sys.exit(hw_route.route('b', ['g']))",
        ])
        run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-1500:])
        board = pcbnew.LoadBoard(str(self.path))
        self.assertEqual(self.copper(board), [("PCB_TRACK", "N1", 100.0, 100.0, 102.0, 100.0)])


if __name__ == "__main__":
    unittest.main()
