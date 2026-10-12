"""Perch board: pins and pads line up with the owl, and the dock link matches the main board."""

import ast
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


def perch_constants() -> dict:
    """Literal constants of enclosure/perch_v1.py (parsed, so this test needs no build123d)."""
    tree = ast.parse((ROOT / "enclosure" / "perch_v1.py").read_text())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def enclosure_errors(board, q: dict, heights: dict) -> list[str]:
    """Where the perch board no longer fits perch_v1's pocket, cavity, bosses and J1 box."""
    import pcbnew

    refs = {fp.GetReference(): fp for fp in board.GetFootprints()}
    cx, cy = (pcbnew.ToMM(v) for v in refs["P2"].GetPosition())

    def box(fp, layer):
        shapes = [g for g in fp.GraphicalItems() if g.GetLayer() == layer]
        xs = [pcbnew.ToMM(v) - cx for g in shapes for v in (g.GetBoundingBox().GetLeft(), g.GetBoundingBox().GetRight())]
        ys = [cy - pcbnew.ToMM(v) for g in shapes for v in (g.GetBoundingBox().GetTop(), g.GetBoundingBox().GetBottom())]
        return min(xs), max(xs), min(ys), max(ys)

    errors = []
    for ref, (hx, ha) in zip(("H1", "H2"), q["HOLES"]):
        x, y = (pcbnew.ToMM(v) for v in refs[ref].GetPosition())
        if abs(x - cx - hx) > 0.01 or abs(cy - y - ha) > 0.01:
            errors.append(f"{ref} at ({x - cx:.2f}, {cy - y:.2f}) from P2, perch_v1 HOLES says ({hx}, {ha})")
    w, h, _ = q["PERCH_BOARD"]
    x0, x1, half, deep = q["J1_BOX"]
    for ref, fp in refs.items():
        if fp.IsFlipped() or ref.startswith(("P", "H", "MB", "J2")):
            continue
        if cy - pcbnew.ToMM(fp.GetPosition().y) < -h / 2:
            continue  # pad section
        if ref == "J1":
            left, right, low, high = box(fp, pcbnew.F_Fab)
            if left < x0 or right > x1 or low < q["J1_ALONG"] - half or high > q["J1_ALONG"] + half:
                errors.append(f"J1 body x {left:.2f}..{right:.2f}, along {low:.2f}..{high:.2f} outside J1_BOX")
            if heights[ref] > deep:
                errors.append(f"J1 height {heights[ref]} above the J1 cavity depth {deep}")
            continue
        left, right, low, high = box(fp, pcbnew.F_CrtYd)
        if left < q["PARTS_X"][0] or right > q["PARTS_X"][1] or low < -h / 2 or high > h / 2:
            errors.append(f"{ref} courtyard x {left:.2f}..{right:.2f}, along {low:.2f}..{high:.2f} outside PARTS_X or the board")
        if heights[ref] > q["PARTS_H"]:
            errors.append(f"{ref} height {heights[ref]} above PARTS_H {q['PARTS_H']}")
    return errors


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

    def load_board(self):
        try:
            import pcbnew
        except ImportError:
            self.skipTest("needs KiCad's pcbnew module")
        pcb = PERCH / "perch-dock.kicad_pcb"
        board = pcbnew.LoadBoard(str(pcb)) if pcb.exists() else None
        if board is None or "P2" not in {fp.GetReference() for fp in board.GetFootprints()}:
            self.skipTest("perch board not placed yet")
        return board

    def test_perch_v1_constants_match_the_board(self):
        # R49: perch_v1's pocket, cavity, bosses and J1 box follow the KiCad board
        board = self.load_board()
        heights = {ref: p["height"] for ref, p in self.perch.items()}
        self.assertEqual(enclosure_errors(board, perch_constants(), heights), [])

    def test_constants_check_catches_a_moved_part(self):
        board = self.load_board()
        import pcbnew  # after load_board, which skips without KiCad

        heights = {ref: p["height"] for ref, p in self.perch.items()}
        refs = {fp.GetReference(): fp for fp in board.GetFootprints()}
        refs["LED1"].Move(pcbnew.VECTOR2I(pcbnew.FromMM(-1.0), 0))
        refs["H1"].Move(pcbnew.VECTOR2I(0, pcbnew.FromMM(0.5)))
        errors = enclosure_errors(board, perch_constants(), heights)
        self.assertTrue(any(e.startswith("LED1") for e in errors), errors)
        self.assertTrue(any(e.startswith("H1") for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
