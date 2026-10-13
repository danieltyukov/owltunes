"""Design rules on hardware/owl-mainboard/design.toml (the schematic must match that file).

Each test names the sheets it needs and is skipped until they exist, so the file can be written
before the schematic is drawn sheet by sheet.
"""

import collections
import pathlib
import re
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DESIGN = ROOT / "hardware" / "owl-mainboard" / "design.toml"
ALL_SHEETS = {"power", "mcu_usb", "periph"}
RAILS = {"+3V3", "DISP_3V3", "DISP_1V8", "VSYS", "VBAT", "VIN_CHG"}

# VIEWE ALL-UEOL018VG-RA31-A001A spec V1.1, page 7 (I/O connection), and page 12 (QSPI wiring).
# The touch pins are on the 1.8 V side of U305 (VIEWE, 13 October 2026).
PANEL = {1: "GND", 2: "TP_INT_1V8", 3: "TP_RST_1V8", 4: "TP_SDA_1V8", 5: "TP_SCL_1V8",
         6: "DISP_3V3", 7: "GND", 8: "DISP_3V3", 9: "DISP_3V3", 10: "DISP_3V3", 11: "DISP_3V3",
         12: "GND", 13: None, 14: "LCD_RST", 15: "LCD_CS", 16: "LCD_D0", 17: "LCD_D1",
         18: "LCD_CLK", 19: "LCD_D3", 20: "LCD_D2", 21: "LCD_TE", 22: "GND", 23: None, 24: None,
         25: "GND", 26: None, 27: None, 28: "GND", 29: None, 30: None, 31: "GND"}


def load():
    parts = tomllib.loads(DESIGN.read_text())["part"]
    return {p["ref"]: p for p in parts}


def nets(parts):
    out = collections.defaultdict(set)
    for ref, p in parts.items():
        for pin, net in p.get("pins", {}).items():
            out[net].add(f"{ref}.{pin}")
    return out


def resistors_between(parts, a, b):
    return [r for r, p in parts.items() if p["symbol"] == "Device:R" and set(p["pins"].values()) == {a, b}]


class DesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = load()
        cls.sheets = {p["sheet"] for p in cls.parts.values()}
        cls.nets = nets(cls.parts)

    def need(self, *sheets):
        missing = set(sheets) - self.sheets
        if missing:
            self.skipTest(f"needs sheet(s) {sorted(missing)}")

    def test_parts_are_well_formed(self):
        for ref, p in self.parts.items():
            self.assertIn(p["sheet"], ALL_SHEETS, ref)
            self.assertIn(p.get("side"), ("front", "back"), ref)
            self.assertGreaterEqual(p.get("height", -1), 0.0, ref)
            if p.get("assembled", True):
                self.assertRegex(p.get("lcsc", ""), r"^C\d+$", ref)
                self.assertTrue(p.get("mpn") and p.get("manufacturer"), ref)
            self.assertFalse(set(p.get("pins", {})) & set(p.get("nc", [])), ref)

    def test_every_net_has_two_pins(self):
        self.need(*ALL_SHEETS)
        lonely = {n: m for n, m in self.nets.items() if len(m) < 2}
        self.assertEqual(lonely, {})

    def test_power_inputs_are_diode_ored(self):
        self.need(*ALL_SHEETS)
        p = self.parts
        self.assertEqual((p["D101"]["symbol"], p["D101"]["pins"]), ("Device:D_Schottky", {"1": "VIN_CHG", "2": "VBUS_USB"}))
        self.assertEqual((p["D102"]["symbol"], p["D102"]["pins"]), ("Device:D_Schottky", {"1": "VIN_CHG", "2": "VBUS_DOCK"}))
        for vbus, tvs in (("VBUS_USB", "D201"), ("VBUS_DOCK", "D301")):
            self.assertEqual(p[tvs]["pins"], {"1": vbus, "2": "GND"})
            others = {pin.split(".")[0] for pin in self.nets[vbus]} - {"D101", "D102", tvs, "J201", "U202", "J303"}
            self.assertEqual(others, set(), vbus)
        self.assertEqual(p["U101"]["pins"]["13"], "VIN_CHG")

    def test_strap_pins_have_their_pulls(self):
        self.need("power", "mcu_usb")
        u = self.parts["U201"]["pins"]
        self.assertEqual((u["27"], u["26"], u["16"]), ("BOOT", "CHG_SUSPEND", "DISP_EN"))
        self.assertTrue(resistors_between(self.parts, "+3V3", "BOOT"))
        self.assertTrue(resistors_between(self.parts, "CHG_SUSPEND", "GND"))
        self.assertTrue(resistors_between(self.parts, "DISP_EN", "GND"))

    def test_display_fpc_map_mirrors_the_panel(self):
        self.need("periph")
        j = self.parts["J301"]
        for k in range(1, 32):
            want = PANEL[32 - k]
            if want is None:
                self.assertIn(str(k), j["nc"], k)
            else:
                self.assertEqual(j["pins"].get(str(k)), want, k)

    def test_bus_pullups_follow_their_rails(self):
        self.need(*ALL_SHEETS)
        for sig in ("TP_SDA", "TP_SCL", "TP_INT"):
            self.assertTrue(resistors_between(self.parts, "DISP_3V3", sig), sig)
            self.assertFalse(resistors_between(self.parts, "+3V3", sig), sig)
        for sig in ("TP_SDA_1V8", "TP_SCL_1V8", "TP_INT_1V8", "TP_RST_1V8"):
            self.assertTrue(resistors_between(self.parts, "DISP_1V8", sig), sig)
            self.assertFalse(resistors_between(self.parts, "DISP_3V3", sig), sig)
            self.assertFalse(resistors_between(self.parts, "+3V3", sig), sig)
        for sig in ("I2C_SDA", "I2C_SCL"):
            self.assertTrue(resistors_between(self.parts, "+3V3", sig), sig)
            self.assertFalse(resistors_between(self.parts, "DISP_3V3", sig), sig)
            for ref in {pin.split(".")[0] for pin in self.nets[sig]}:
                supplies = set(self.parts[ref].get("pins", {}).values()) & RAILS
                self.assertNotIn("DISP_3V3", supplies, f"{ref} on {sig} must not be powered from DISP_3V3")

    def test_touch_side_runs_from_the_panel_rail(self):
        # DISP_1V8 comes from DISP_3V3 and U305's refB is DISP_3V3, so with the panel off nothing
        # can hold the touch controller up (Review Focus 2).
        self.need("periph")
        p = self.parts
        self.assertEqual((p["U306"]["pins"]["3"], p["U306"]["pins"]["2"]), ("DISP_3V3", "DISP_1V8"))
        u = p["U305"]["pins"]
        self.assertEqual((u["14"], u["1"], u["8"]), ("DISP_3V3", "DISP_1V8", "DISP_1V8"))
        touch = {n for n in self.nets if n.startswith("TP_") and n.endswith("_1V8")}
        self.assertEqual(touch, {"TP_SDA_1V8", "TP_SCL_1V8", "TP_INT_1V8", "TP_RST_1V8"})
        for net in touch:
            allowed = {"J301", "U305", *resistors_between(p, "DISP_1V8", net)}
            for ref in {pin.split(".")[0] for pin in self.nets[net]}:
                self.assertIn(ref, allowed, net)
        self.assertTrue(resistors_between(p, "DISP_1V8", "GND"))
        on_rail = {pin.split(".")[0] for pin in self.nets["DISP_1V8"]}
        resistors = {r for r in on_rail if p[r]["symbol"] == "Device:R"}
        others = {r for r in resistors if not set(p[r]["pins"].values()) & (touch | {"GND"})}
        self.assertEqual(others, {"R315"})
        self.assertEqual(set(p["R315"]["pins"].values()), {"DISP_1V8", "DISP_3V3"})
        self.assertFalse(p["R315"].get("assembled", True))

    def test_wake_nets_have_pullups(self):
        self.need(*ALL_SHEETS)
        u = self.parts["U201"]["pins"]
        wake = {"39": "DOCK_DET", "38": "BTN_EAR_L", "15": "BTN_EAR_R", "4": "BTN_BEAK", "5": "HALL_INT", "7": "CHG_PGOOD"}
        for pin, net in wake.items():
            self.assertEqual(u[pin], net)
            self.assertTrue(resistors_between(self.parts, "+3V3", net), net)
        self.assertEqual(u["6"], "IMU_INT1")  # push-pull, configured active low by firmware

    def test_every_ic_rail_has_a_capacitor(self):
        self.need(*ALL_SHEETS)
        caps = {net for p in self.parts.values() if p["symbol"] == "Device:C" for net in p["pins"].values()}
        for ref, p in self.parts.items():
            if re.match(r"U\d", ref):
                for rail in set(p.get("pins", {}).values()) & RAILS:
                    self.assertIn(rail, caps, f"{ref} {rail}")


if __name__ == "__main__":
    unittest.main()
