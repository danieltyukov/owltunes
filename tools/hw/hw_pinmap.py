#!/usr/bin/env python3
"""Check firmware/main/board_owltunes_reva.h against the main board netlist.

Every `#define OWL_PIN_<NET> <gpio>` must name the net on the ESP32-S3-WROOM-1 pin that carries
that GPIO, and every module GPIO pin that is on a named net (other than GND and +3V3) must have a
macro. Usage: python3 tools/hw/hw_pinmap.py
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

from hw_netlist import ROOT, export_netlist, read_netlist

MODULE = "U201"
# ESP32-S3-WROOM-1 module pin -> GPIO (KiCad symbol RF_Module:ESP32-S3-WROOM-1, Espressif datasheet table 3-1).
PIN_TO_GPIO = {
    "4": 4, "5": 5, "6": 6, "7": 7, "8": 15, "9": 16, "10": 17, "11": 18, "12": 8, "13": 19,
    "14": 20, "15": 3, "16": 46, "17": 9, "18": 10, "19": 11, "20": 12, "21": 13, "22": 14,
    "23": 21, "24": 47, "25": 48, "26": 45, "27": 0, "28": 35, "29": 36, "30": 37, "31": 38,
    "32": 39, "33": 40, "34": 41, "35": 42, "36": 44, "37": 43, "38": 2, "39": 1,
}
DEFINE_RE = re.compile(r"^#define OWL_PIN_([A-Z0-9_]+)\s+(\d+)", re.M)


def header_pins(text: str) -> dict[str, int]:
    return {name: int(gpio) for name, gpio in DEFINE_RE.findall(text)}


def check(pins: dict[str, int], nets: dict[str, set[str]]) -> list[str]:
    gpio_net = {}
    for name, members in nets.items():
        for member in members:
            ref, pin = member.split(".")
            if ref == MODULE and pin in PIN_TO_GPIO and not name.startswith("unconnected-"):
                gpio_net[PIN_TO_GPIO[pin]] = name.lstrip("/")
    errors = []
    if not pins:
        errors.append("the header has no OWL_PIN_ macros")
    if not gpio_net:
        errors.append(f"{MODULE} has no GPIO pin on a named net in the netlist")
    for name, gpio in sorted(pins.items()):
        if gpio_net.get(gpio) != name:
            errors.append(f"OWL_PIN_{name} = {gpio}, but GPIO{gpio} is on {gpio_net.get(gpio)!r}")
    named = {gpio: n for gpio, n in gpio_net.items() if n not in ("GND", "+3V3")}
    for gpio, net in sorted(named.items()):
        if pins.get(net) != gpio:
            errors.append(f"GPIO{gpio} carries {net!r} but the header has no OWL_PIN_{net} {gpio}")
    return errors


def main() -> int:
    header = (ROOT / "firmware" / "main" / "board_owltunes_reva.h").read_text()
    schematic = ROOT / "hardware" / "owl-mainboard" / "owl-mainboard.kicad_sch"
    with tempfile.TemporaryDirectory() as tmp:
        nets, _ = read_netlist(export_netlist(schematic, Path(tmp) / "n.xml").read_text())
    errors = check(header_pins(header), nets)
    for e in errors:
        print(e)
    print(f"board_owltunes_reva.h: {len(errors)} pin map error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
