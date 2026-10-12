import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hw"))
from hw_netlist import check, read_netlist  # noqa: E402

NETLIST = """<?xml version="1.0" encoding="UTF-8"?>
<export version="E"><components>
<comp ref="R1"><value>10k</value><footprint>Resistor_SMD:R_0402_1005Metric</footprint>
<libsource lib="Device" part="R" description=""/><property name="Sheetname" value="power"/></comp>
<comp ref="U1"><value>X</value><footprint>Package_TO_SOT_SMD:SOT-23-6</footprint>
<libsource lib="Lib" part="X" description=""/><property name="Sheetname" value="power"/></comp>
</components><nets>
<net code="1" name="+3V3"><node ref="R1" pin="1"/><node ref="U1" pin="1"/></net>
<net code="2" name="SIG"><node ref="R1" pin="2"/><node ref="U1" pin="2"/></net>
<net code="3" name="unconnected-(U1-Pad3)"><node ref="U1" pin="3"/></net>
</nets></export>"""


def design(**changes):
    parts = [
        {"ref": "R1", "sheet": "power", "symbol": "Device:R", "footprint": "Resistor_SMD:R_0402_1005Metric",
         "value": "10k", "pins": {"1": "+3V3", "2": "SIG"}},
        {"ref": "U1", "sheet": "power", "symbol": "Lib:X", "footprint": "Package_TO_SOT_SMD:SOT-23-6",
         "value": "X", "pins": {"1": "+3V3", "2": "SIG"}, "nc": ["3"]},
    ]
    for ref, patch in changes.items():
        next(p for p in parts if p["ref"] == ref).update(patch)
    return {"part": parts}


class NetlistCheckTest(unittest.TestCase):
    def setUp(self):
        self.nets, self.comps = read_netlist(NETLIST)

    def test_matching_design_passes(self):
        self.assertEqual(check(design(), self.nets, self.comps), [])

    def test_pin_on_wrong_net_is_reported(self):
        errors = check(design(R1={"pins": {"1": "VSYS", "2": "SIG"}}), self.nets, self.comps)
        self.assertIn("R1.1 is on '+3V3', design says 'VSYS'", errors)

    def test_undeclared_pin_on_a_net_is_reported(self):
        errors = check(design(U1={"pins": {"1": "+3V3"}, "nc": ["3"]}), self.nets, self.comps)
        self.assertIn("U1.2 is on 'SIG' but design.toml does not list the pin", errors)

    def test_wrong_footprint_and_missing_part(self):
        d = design(R1={"footprint": "Resistor_SMD:R_0603_1608Metric"})
        d["part"].append({"ref": "C1", "sheet": "power", "symbol": "Device:C", "footprint": "", "value": "1u"})
        errors = check(d, self.nets, self.comps)
        self.assertIn("missing part C1", errors)
        self.assertTrue(any(e.startswith("R1 footprint") for e in errors))

    def test_sheet_filter_ignores_other_sheets(self):
        d = design()
        d["part"].append({"ref": "C9", "sheet": "periph", "symbol": "Device:C", "footprint": "", "value": "1u"})
        self.assertEqual(check(d, self.nets, self.comps, {"power"}), [])

    def test_nc_pin_that_is_connected_is_reported(self):
        d = design(U1={"pins": {"1": "+3V3"}, "nc": ["2"]})
        errors = check(d, self.nets, self.comps)
        self.assertIn("U1.2 must be unconnected but is on 'SIG'", errors)

    def test_part_missing_from_design_is_reported(self):
        d = design()
        d["part"] = [p for p in d["part"] if p["ref"] != "R1"]
        self.assertIn("part R1 is not in design.toml", check(d, self.nets, self.comps))

    def test_symbol_and_value_mismatches_are_reported(self):
        errors = check(design(R1={"symbol": "Device:C", "value": "4k7"}), self.nets, self.comps)
        self.assertIn("R1 symbol is 'Device:R', design says 'Device:C'", errors)
        self.assertIn("R1 value is '10k', design says '4k7'", errors)


if __name__ == "__main__":
    unittest.main()
