import pathlib
import sys
import tomllib
import unittest

HW = pathlib.Path(__file__).resolve().parent.parent / "hw"
sys.path.insert(0, str(HW))
import hw_stackup  # noqa: E402

ROOT = HW.parent.parent
PCB = '(kicad_pcb\n\t(setup\n\t\t(pad_to_mask_clearance 0)\n\t)\n)\n'


def setup(board):
    return tomllib.loads((ROOT / "hardware" / board / "setup.toml").read_text())


class StackupTest(unittest.TestCase):
    def test_real_boards_stack_up_to_their_thickness(self):
        for board, layers, thickness in (("owl-mainboard", 4, 1.0), ("perch-dock", 2, 1.6)):
            cfg = setup(board)
            self.assertEqual(hw_stackup.validate(cfg), [], board)
            self.assertAlmostEqual(hw_stackup.total_mm(cfg), thickness, places=2)
            self.assertEqual(cfg["copper_layers"], layers)

    def test_wrong_total_or_layer_count_is_reported(self):
        cfg = setup("perch-dock")
        cfg["thickness_mm"] = 1.0
        self.assertEqual(len(hw_stackup.validate(cfg)), 1)
        cfg = setup("perch-dock")
        cfg["copper_layers"] = 4
        self.assertEqual(len(hw_stackup.validate(cfg)), 1)

    def test_apply_is_idempotent_and_keeps_the_rest_of_setup(self):
        cfg = setup("owl-mainboard")
        once = hw_stackup.apply(PCB, cfg)
        self.assertEqual(hw_stackup.apply(once, cfg), once)
        self.assertEqual(once.count("(stackup"), 1)
        self.assertIn("\t\t(pad_to_mask_clearance 0)\n", once)
        self.assertEqual(once.count("(type \"copper\")"), 4)

    def test_the_committed_pcbs_carry_the_stackup(self):
        for board in ("owl-mainboard", "perch-dock"):
            text = (ROOT / "hardware" / board / f"{board}.kicad_pcb").read_text()
            self.assertEqual(hw_stackup.apply(text, setup(board)), text, board)


if __name__ == "__main__":
    unittest.main()
