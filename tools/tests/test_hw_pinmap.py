import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hw"))
from hw_pinmap import check, header_pins  # noqa: E402

HEADER = """
#define OWL_PIN_LCD_CS 10
#define OWL_PIN_BOOT 0
#define OWL_I2C_ADDR_X 0x35
"""
NETS = {"LCD_CS": {"U201.18", "J301.17"}, "BOOT": {"U201.27", "R206.2"}, "GND": {"U201.1"}}


class PinmapTest(unittest.TestCase):
    def test_header_parsing_ignores_other_macros(self):
        self.assertEqual(header_pins(HEADER), {"LCD_CS": 10, "BOOT": 0})

    def test_matching_map_passes(self):
        self.assertEqual(check({"LCD_CS": 10, "BOOT": 0}, NETS), [])

    def test_wrong_gpio_and_missing_macro_are_reported(self):
        errors = check({"LCD_CS": 11}, NETS)
        self.assertIn("OWL_PIN_LCD_CS = 11, but GPIO11 is on None", errors)
        self.assertIn("GPIO0 carries 'BOOT' but the header has no OWL_PIN_BOOT 0", errors)

    def test_empty_header_or_missing_module_is_an_error(self):
        self.assertIn("the header has no OWL_PIN_ macros", check({}, NETS))
        errors = check({}, {"GND": {"U1.1"}})
        self.assertIn("the header has no OWL_PIN_ macros", errors)
        self.assertIn("U201 has no GPIO pin on a named net in the netlist", errors)

    def test_unconnected_module_pins_need_no_macro(self):
        nets = dict(NETS, **{"unconnected-(U201-IO35-Pad28)": {"U201.28"}})
        self.assertEqual(check({"LCD_CS": 10, "BOOT": 0}, nets), [])


if __name__ == "__main__":
    unittest.main()
