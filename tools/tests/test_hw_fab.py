import pathlib
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hw"))
try:
    import pcbnew  # noqa: F401  (KiCad's module; CI runs in the KiCad container)
except ImportError:
    pcbnew = None
if pcbnew is not None:
    from hw_fab import LAYERS, symbol_errors, verify

BOM = "﻿Designator,Footprint,Quantity,Value,LCSC Part #\n"
CPL = "﻿Designator,Mid X,Mid Y,Rotation,Layer\n"
DESIGN = {"part": [
    {"ref": "U1", "lcsc": "C15220", "side": "back"},
    {"ref": "SW1", "lcsc": "C720477", "side": "front"},
    {"ref": "TP1", "side": "back", "assembled": False},
]}


@unittest.skipIf(pcbnew is None, "needs KiCad's pcbnew module")
class FabVerifyTest(unittest.TestCase):
    def write(self, bom_rows, pos_rows, layers=None):
        out = pathlib.Path(self.tmp.name)
        with zipfile.ZipFile(out / "b.zip", "w") as z:
            for layer in layers if layers is not None else LAYERS[4]:
                z.writestr(f"b-{layer}.gbr", "")
            z.writestr("b-PTH.drl", "")
        (out / "bom.csv").write_text(BOM + bom_rows, encoding="utf-8")
        (out / "positions.csv").write_text(CPL + pos_rows, encoding="utf-8")
        return out

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_matching_outputs_pass(self):
        out = self.write('U1,QFN,1,BQ,C15220\nSW1,SW,1,Beak,C720477\n', "U1,0,0,90,bottom\nSW1,0,-35,0,top\n")
        self.assertEqual(verify(out, "b", DESIGN, 4), [])

    def test_missing_layer_wrong_lcsc_extra_part_and_wrong_side_fail(self):
        layers = [x for x in LAYERS[4] if x != "In2_Cu"]
        out = self.write('U1,QFN,1,BQ,C15464\n"SW1, TP1",SW,2,Beak,C720477\n', "U1,0,0,90,top\nSW1,0,-35,0,top\n", layers)
        errors = verify(out, "b", DESIGN, 4)
        self.assertIn("gerber layer In2_Cu missing", errors)
        self.assertIn("U1: BOM LCSC 'C15464', design 'C15220'", errors)
        self.assertIn("BOM refs differ: extra ['TP1'], missing []", errors)
        self.assertIn("U1: CPL layer top, design side back", errors)

    def test_duplicate_designators_and_wrong_quantity_fail(self):
        good_pos = "U1,0,0,90,bottom\nSW1,0,-35,0,top\n"
        out = self.write('U1,QFN,1,BQ,C15220\nSW1,SW,1,Beak,C720477\nSW1,SW,1,Beak,C720477\n', good_pos)
        self.assertIn("BOM lists SW1 more than once", verify(out, "b", DESIGN, 4))
        out = self.write('U1,QFN,1,BQ,C15220\nSW1,SW,1,Beak,C720477\n', good_pos + "SW1,0,-35,0,top\n")
        self.assertIn("CPL lists SW1 more than once", verify(out, "b", DESIGN, 4))
        out = self.write('U1,QFN,2,BQ,C15220\nSW1,SW,1,Beak,C720477\n', good_pos)
        self.assertIn("BOM row 'U1' has quantity 2 for 1 designator(s)", verify(out, "b", DESIGN, 4))

    def test_npth_only_drill_fails(self):
        out = self.write('U1,QFN,1,BQ,C15220\nSW1,SW,1,Beak,C720477\n', "U1,0,0,90,bottom\nSW1,0,-35,0,top\n")
        with zipfile.ZipFile(out / "b.zip", "w") as z:
            for layer in LAYERS[4]:
                z.writestr(f"b-{layer}.gbr", "")
            z.writestr("b-NPTH.drl", "")
        self.assertIn("drill file missing", verify(out, "b", DESIGN, 4))

    def test_assembled_part_without_lcsc_is_an_error_not_a_crash(self):
        design = {"part": DESIGN["part"] + [{"ref": "C9", "side": "front"}]}
        out = self.write('U1,QFN,1,BQ,C15220\nSW1,SW,1,Beak,C720477\nC9,0402,1,1u,C1\n',
                         "U1,0,0,90,bottom\nSW1,0,-35,0,top\nC9,0,0,0,top\n")
        self.assertIn("C9: assembled part has no lcsc in design.toml", verify(out, "b", design, 4))


@unittest.skipIf(pcbnew is None, "needs KiCad's pcbnew module")
class SymbolExclusionTest(unittest.TestCase):
    SCH = (
        "(kicad_sch\n\t(symbol\n\t\t(lib_id \"Connector:TestPoint\")\n\t\t(in_bom %s)\n\t\t(on_board yes)\n"
        "\t\t(property \"Reference\" \"%s\"\n\t\t)\n\t)\n)\n"
    )

    def test_symbol_without_in_bom_no_is_named(self):
        texts = [self.SCH % ("no", "TP1"), self.SCH % ("yes", "TP2")]
        errors = symbol_errors(texts, ["TP1", "TP2", "TP3"])
        self.assertEqual(errors, [
            "TP2: schematic symbol is in the BOM, set (in_bom no) (Exclude from BOM)",
            "TP3: no schematic symbol found",
        ])


if __name__ == "__main__":
    unittest.main()
