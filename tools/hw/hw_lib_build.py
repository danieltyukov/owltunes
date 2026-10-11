#!/usr/bin/env python3
"""Build hardware/lib: symbols, footprints and 3D models for the parts KiCad's library lacks.

Symbols are drawn from the datasheet pin tables in PARTS, footprints from the manufacturers'
land patterns in FOOTPRINTS (pages cited there and in hardware/lib/README.md). Each footprint
keeps the orientation of the part's LCSC/EasyEDA footprint, which is JLC's zero rotation, so the
placement file needs no rotation offset for these parts. ESP32-S3-WROOM-1_Drill0.3 is KiCad's
module footprint with its twelve thermal vias opened from 0.2 to 0.3 mm (JLCPCB's no-fee size;
the 0.6 mm pads keep a 0.15 mm ring).

JLC2KiCadLib downloads the EasyEDA symbols, footprints and STEP models into build/jlclib (or the
script reads them from --from DIR). The STEP models are copied to hardware/lib/3dmodels, which
is not tracked because EasyEDA's licence is unclear; the EasyEDA pin names and pads are compared
with the tables here as a second source and the differences printed. --offline skips the
download, the models and the comparison and writes only the tracked files.

Symbols and footprints are written through kicad-cli (sym upgrade, fp upgrade), so they are what
KiCad itself saves; footprint uuids are derived from the footprint name, so a rebuild gives the
same files. Other files in hardware/lib (hand-made footprints) are left alone.

Usage: python3 tools/hw/hw_lib_build.py [--from build/jlclib | --offline] [--lib DIR]
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from hw_netlist import ROOT

LIB = ROOT / "hardware" / "lib"
MODEL_PATH = "${KIPRJMOD}/../lib/3dmodels"
STOCK_FOOTPRINTS = Path("/usr/share/kicad/footprints")
UUID_NS = uuid.UUID("6f0b2a4e-0f1d-4c2b-9a51-3d0c7a1e5b20")

# --------------------------------------------------------------------------------------------
# Symbols: pin number -> (name, electrical type), and which side of the box each pin is on.
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Part:
    lcsc: str
    footprint: str
    datasheet: str
    description: str
    keywords: str
    pins: dict[str, tuple[str, str]]
    left: tuple[str, ...] = ()
    right: tuple[str, ...] = ()
    top: tuple[str, ...] = ()
    bottom: tuple[str, ...] = ()


PARTS = {
    # TPS63802 datasheet SLVSEU9D, table 7-1 (p. 4).
    "TPS63802DLAR": Part(
        "C2845237", "owltunes:TI_DLA_VSON-10_2x3mm_P0.5mm", "https://www.ti.com/lit/ds/symlink/tps63802.pdf",
        "Buck-boost converter, 1.3 V to 5.5 V in, 2 A, VSON-HR-10 2 x 3 mm", "buck boost regulator TI",
        {"1": ("EN", "input"), "2": ("MODE", "input"), "3": ("AGND", "power_in"), "4": ("FB", "input"),
         "5": ("PG", "open_collector"), "6": ("VOUT", "power_out"), "7": ("L2", "passive"),
         "8": ("GND", "power_in"), "9": ("L1", "passive"), "10": ("VIN", "power_in")},
        left=("10", "9", "1", "2"), right=("6", "7", "4", "5"), bottom=("3", "8")),
    # MAX17048 datasheet 19-6171 rev 7, pin description (p. 6).
    "MAX17048G+T10": Part(
        "C2682616", "owltunes:Maxim_TDFN-8-1EP_2x2mm_P0.5mm",
        "https://www.analog.com/media/en/technical-documentation/data-sheets/MAX17048-MAX17049.pdf",
        "1-cell fuel gauge with ModelGauge, I2C address 0x36, TDFN-8 2 x 2 mm", "battery fuel gauge Maxim",
        {"1": ("CTG", "input"), "2": ("CELL", "input"), "3": ("VDD", "power_in"), "4": ("GND", "power_in"),
         "5": ("~{ALRT}", "open_collector"), "6": ("QSTRT", "input"), "7": ("SCL", "input"),
         "8": ("SDA", "bidirectional"), "9": ("EP", "passive")},
        left=("2", "6", "1"), right=("8", "7", "5"), top=("3",), bottom=("4", "9")),
    # TMAG5273 datasheet SLYS045C, table 4-1 (p. 4). Pin 3 is a test pin tied to ground.
    "TMAG5273A2QDBVR": Part(
        "C3715882", "Package_TO_SOT_SMD:SOT-23-6", "https://www.ti.com/lit/ds/symlink/tmag5273.pdf",
        "3D linear Hall sensor, I2C, A2: +-133 or +-266 mT, address 0x35, SOT-23-6", "hall magnetic sensor TI",
        {"1": ("SCL", "input"), "2": ("GND", "power_in"), "3": ("GND(TEST)", "passive"), "4": ("VCC", "power_in"),
         "5": ("~{INT}", "open_collector"), "6": ("SDA", "bidirectional")},
        right=("6", "1", "5"), top=("4",), bottom=("2", "3")),
    # LIS2DW12 datasheet DS11811 rev 9, table 1 (p. 4).
    "LIS2DW12TR": Part(
        "C189624", "Package_LGA:LGA-12_2x2mm_P0.5mm", "https://www.st.com/resource/en/datasheet/lis2dw12.pdf",
        "3-axis accelerometer, I2C or SPI, LGA-12 2 x 2 mm", "accelerometer MEMS ST",
        {"1": ("SCL/SPC", "input"), "2": ("CS", "input"), "3": ("SDO/SA0", "bidirectional"),
         "4": ("SDA/SDI/SDO", "bidirectional"), "5": ("NC", "no_connect"), "6": ("GND", "power_in"),
         "7": ("RES", "passive"), "8": ("GND", "power_in"), "9": ("VDD", "power_in"),
         "10": ("VDD_IO", "power_in"), "11": ("INT2", "output"), "12": ("INT1", "output")},
        left=("2", "3", "5"), right=("4", "1", "12", "11"), top=("9", "10"), bottom=("6", "8", "7")),
    # OPT3001 datasheet SBOS681C, pin functions (p. 3); thermal pad from DNP0006A (p. 41).
    "OPT3001DNPR": Part(
        "C90462", "owltunes:TI_DNP_USON-6-1EP_2x2mm_P0.65mm", "https://www.ti.com/lit/ds/symlink/opt3001.pdf",
        "Ambient light sensor, I2C, USON-6 2 x 2 mm", "light sensor lux TI",
        {"1": ("VDD", "power_in"), "2": ("ADDR", "input"), "3": ("GND", "power_in"), "4": ("SCL", "input"),
         "5": ("~{INT}", "open_collector"), "6": ("SDA", "bidirectional"), "7": ("EP", "passive")},
        left=("2",), right=("6", "4", "5"), top=("1",), bottom=("3", "7")),
}

# --------------------------------------------------------------------------------------------
# Footprints, from the manufacturers' land patterns. KiCad coordinates: mm, X right, Y down.
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pad:
    number: str
    x: float
    y: float
    w: float
    h: float
    shape: str = "rect"  # rect, roundrect, oval or circle
    kind: str = "smd"  # smd or thru_hole
    rratio: float = 0.0  # roundrect corner radius over the shorter side
    drill: float = 0.0
    paste: tuple[float, float] | None = None  # stencil aperture (w, h) when the datasheet reduces it
    exposed: bool = False  # exposed pad: heat sink property, solid zone connection
    layers: tuple[str, ...] = ("F.Cu", "F.Mask", "F.Paste")  # smd pads; ("F.Paste",) is a stencil opening
    ring: tuple[float, float] | None = None  # custom paste pad: ring (radius, width) round the origin

    @property
    def copper(self) -> bool:
        return self.kind == "thru_hole" or "F.Cu" in self.layers


@dataclass(frozen=True)
class Footprint:
    lcsc: str  # the part whose EasyEDA footprint and STEP model are used
    easyeda: str  # EasyEDA footprint name
    descr: str
    tags: str
    body: tuple[float, float, float, float]  # x0, y0, x1, y1 of the package outline
    pads: tuple[Pad, ...]
    round_body: bool = False
    pin1: bool = True  # silkscreen dot beside pad 1
    model_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    model_rotate: tuple[float, float, float] = (0.0, 0.0, 0.0)
    model_scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    keepout: tuple[float, float, float, float] | None = None  # no tracks, vias or pour on F.Cu
    fpc_arrow: bool = False


def column(first: int, x: float, y0: float, pitch: float, count: int, w: float, h: float, **kw) -> list[Pad]:
    return [Pad(str(first + i), x, round(y0 + i * pitch, 6), w, h, **kw) for i in range(count)]


def row(numbers: list[int], x0: float, y: float, pitch: float, w: float, h: float, **kw) -> list[Pad]:
    return [Pad(str(n), round(x0 + i * pitch, 6), y, w, h, **kw) for i, n in enumerate(numbers)]


def dla0010a() -> tuple[Pad, ...]:
    """TPS63802 SLVSEU9D p. 36, DLA0010A example board layout: 0.25 wide pads on 0.5 pitch with
    R0.05 corners; pins 1-5 0.6 long centred 0.9 left of the package centre line, pins 6, 7, 9
    and 10 0.9 long centred 0.75 right of it, pin 8 (GND) 1.3 long centred 0.55 right of it.
    Stencil p. 37: pad 8 printed at 83 % (here one 1.1 x 0.25 aperture, the same area)."""
    kw = {"shape": "roundrect", "rratio": 0.2}
    pads = column(1, -0.9, -1.0, 0.5, 5, 0.6, 0.25, **kw)
    pads += [Pad(str(n), 0.75, y, 0.9, 0.25, **kw) for n, y in ((6, 1.0), (7, 0.5), (9, -0.5), (10, -1.0))]
    pads.append(Pad("8", 0.55, 0.0, 1.3, 0.25, paste=(1.1, 0.25), **kw))
    return tuple(sorted(pads, key=lambda p: int(p.number)))


def maxim_90_0065() -> tuple[Pad, ...]:
    """Maxim land pattern 90-0065 rev E (8L TDFN 2 x 2, package code T822): pads 0.30 x 0.70 on
    0.50 pitch, row centres 1.98 apart, exposed pad 0.80 x 1.38. Turned to the MAX17048 top view
    (datasheet p. 6, also EasyEDA's): pins 1-4 along the bottom from the left, 5-8 along the top
    from the right. No stencil is given; the exposed pad prints 0.05 mm in from its edge (81 %)."""
    pads = row([1, 2, 3, 4], -0.75, 0.99, 0.5, 0.30, 0.70) + row([8, 7, 6, 5], -0.75, -0.99, 0.5, 0.30, 0.70)
    pads.append(Pad("9", 0.0, 0.0, 1.38, 0.80, paste=(1.28, 0.70), exposed=True))
    return tuple(sorted(pads, key=lambda p: int(p.number)))


def dnp0006a() -> tuple[Pad, ...]:
    """OPT3001 SBOS681C p. 42, DNP0006A example board layout: obround pads 0.5 x 0.25 on 0.65
    pitch, row centres 1.9 apart, thermal pad 0.65 x 1.35 (the 0.2 mm vias drawn there are left
    to layout). Turned to EasyEDA's orientation: pins 1-3 along the bottom from the left. Stencil
    p. 43: thermal pad aperture 0.62 x 1.25 (88 %)."""
    pads = row([1, 2, 3], -0.65, 0.95, 0.65, 0.25, 0.5, shape="oval")
    pads += row([6, 5, 4], -0.65, -0.95, 0.65, 0.25, 0.5, shape="oval")
    pads.append(Pad("7", 0.0, 0.0, 1.35, 0.65, paste=(1.25, 0.62), exposed=True))
    return tuple(sorted(pads, key=lambda p: int(p.number)))


def fh26w(n: int = 31) -> tuple[Pad, ...]:
    """Hirose FH26W catalogue EDC3-323714-05 p. 1, recommended PCB mounting pattern: 0.3 wide
    contacts, 0.6 pitch in each row and 0.3 overall; odd contacts on the FPC side 0.8 long, even
    contacts 0.65 long, 2.15 between the rows (3.6 overall); fitting tabs 0.4 x 0.95, 0.5 beyond
    the outer odd contacts, 0.2 in from the odd row's outer edge. 31 contacts: C = 9.0, B = 8.4
    (p. 4). Origin midway between the row centres; contact 1 at the left of the FPC side."""
    odd_y = (0.65 / 2 + 2.15 + 0.8 / 2) / 2  # row centres 2.875 apart
    cu = ("F.Cu", "F.Mask")  # the stencil openings below are separate pads
    pads = [Pad(str(k), round((k - (n + 1) / 2) * 0.3, 6), odd_y if k % 2 else -odd_y, 0.3, 0.8 if k % 2 else 0.65,
                layers=cu) for k in range(1, n + 1)]
    tab_x = round((n - 1) / 2 * 0.3 + 0.5 + 0.4 / 2, 6)
    tab_y = round(odd_y + 0.8 / 2 - 0.2 - 0.95 / 2, 6)
    pads += [Pad("MP", -tab_x, tab_y, 0.4, 0.95, layers=cu), Pad("MP", tab_x, tab_y, 0.4, 0.95, layers=cu)]
    # Recommended stencil pattern (t = 0.1), same page: openings 0.23 wide, even row 0.55 and odd row
    # 0.65 long, flush with the pads' outer ends (2.4 apart, 3.6 overall); tab openings 0.3 x 0.7 on
    # the tab's outer side, outer edge 0.9 from the outer odd contact, lower edge 0.2 up from the odd
    # row's end. KiCad's paste margins shrink a pad evenly, so these are paste-only pads.
    odd_end, even_end = odd_y + 0.8 / 2, -odd_y - 0.65 / 2
    paste = ("F.Paste",)
    pads += [Pad("", round((k - (n + 1) / 2) * 0.3, 6),
                 round(odd_end - 0.65 / 2, 6) if k % 2 else round(even_end + 0.55 / 2, 6),
                 0.23, 0.65 if k % 2 else 0.55, layers=paste) for k in range(1, n + 1)]
    open_x = round((n - 1) / 2 * 0.3 + 0.9 - 0.3 / 2, 6)
    open_y = round(odd_end - 0.2 - 0.7 / 2, 6)
    pads += [Pad("", -open_x, open_y, 0.3, 0.7, layers=paste), Pad("", open_x, open_y, 0.3, 0.7, layers=paste)]
    return tuple(pads)


def dfe201612e() -> tuple[Pad, ...]:
    """Murata DFE201612E reference specification J(E)TE243A-0006B-01 p. 5: pads 0.8 x 1.8, 0.8
    apart (2.4 overall)."""
    return Pad("1", -0.8, 0.0, 0.8, 1.8), Pad("2", 0.8, 0.0, 0.8, 1.8)


FOOTPRINTS = {
    "TI_DLA_VSON-10_2x3mm_P0.5mm": Footprint(
        "C2845237", "VSON-10_L3.0-W2.0-P0.50-TL",
        "Texas Instruments DLA0010A VSON-HR-10, 2 x 3 mm, 0.5 mm pitch, land pattern from the TPS63802 "
        "datasheet SLVSEU9D p. 36 (https://www.ti.com/lit/ds/symlink/tps63802.pdf)",
        "VSON-HR DLA0010A TPS63802", (-1.0, -1.5, 1.0, 1.5), dla0010a(),
        model_offset=(0.0, 0.0, 0.95)),  # the EasyEDA model's top face is at z = 0
    "Maxim_TDFN-8-1EP_2x2mm_P0.5mm": Footprint(
        "C2682616", "TDFN-8_L2.0-W2.0-P0.50-BL-EP1.2",
        "Maxim TDFN-8 2 x 2 mm with exposed pad (T822), 0.5 mm pitch, land pattern 90-0065 rev E, "
        "MAX17048 datasheet p. 18 (https://www.analog.com/media/en/package-pcb-resources/land-pattern/tdfn/90-0065.pdf)",
        "TDFN T822 MAX17048", (-1.0, -1.0, 1.0, 1.0), maxim_90_0065()),
    "TI_DNP_USON-6-1EP_2x2mm_P0.65mm": Footprint(
        "C90462", "USON6_L2.1-W2.1-P0.65-BL-EP",
        "Texas Instruments DNP0006A USON-6 2 x 2 mm with thermal pad, 0.65 mm pitch, land pattern from the "
        "OPT3001 datasheet SBOS681C p. 42 (https://www.ti.com/lit/ds/symlink/opt3001.pdf)",
        "USON DNP0006A OPT3001", (-1.0, -1.0, 1.0, 1.0), dnp0006a(),
        model_offset=(0.009, 0.013, 0.0), model_rotate=(0.0, 0.0, -90.0)),
    "Hirose_FH26W-31S-0.3SHW_1x31-1MP_P0.30mm_Horizontal": Footprint(
        "C2973806", "CONN-SMD_FH26W-31S-0.3SHW-60",
        "Hirose FH26W-31S-0.3SHW(60) FPC connector, bottom contact, back flip, 31 contacts, 0.3 mm pitch, "
        "recommended PCB mounting pattern from catalogue EDC3-323714-05 p. 1; the FPC enters on the side of "
        "contact 1 (+Y) (https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2206101730_HRS-Hirose-FH26W-31S-0-3SHW-60_C2973806.pdf)",
        "FPC FFC Hirose FH26W bottom contact", (-5.4, -1.28, 5.4, 1.92), fh26w(),
        model_offset=(0.0, -0.179, 0.0), fpc_arrow=True),
    "PogoPin_Xinyangze_YZ71215080P-02": Footprint(
        "C5157364", "SMD_BD2.0-D0.6",
        "Xinyangze YZ71215080P-02 pogo pin, 2.0 mm flange, 0.6 mm locating post, 7.0 mm free height above the "
        "board (drawing YZ71215080P-02, p. 3); 2.2 mm pad, a plated 0.8 mm hole for the post and a ring of "
        "paste clear of the hole "
        "(https://datasheet.lcsc.com/datasheet/pdf/a95fd643b0f3d095f6de25ea57e8af6c.pdf?productCode=C5157364)",
        "pogo pin spring contact", (-1.0, -1.0, 1.0, 1.0),
        (Pad("1", 0.0, 0.0, 2.2, 2.2, shape="circle", layers=("F.Cu", "F.Mask")),
         Pad("1", 0.0, 0.0, 1.1, 1.1, shape="circle", kind="thru_hole", drill=0.8),
         # Paste as a ring from 0.55 mm (0.15 mm clear of the hole) to the pad edge, so none of it
         # runs into the hole. A custom pad anchored on the ring; the anchor lies inside it.
         Pad("", 0.825, 0.0, 0.2, 0.2, shape="custom", layers=("F.Paste",), ring=(0.825, 0.55))),
        round_body=True, pin1=False, model_offset=(0.0, 0.0, -1.4)),  # the model's post is 1.4 long
    "L_Murata_DFE201612E": Footprint(
        "C668312", "IND-SMD_L2.0-W1.6-1",
        "Inductor, Murata DFE201612E, 2.0 x 1.6 x 1.2 mm, recommended PCB pattern from reference "
        "specification J(E)TE243A-0006B-01 p. 5; no copper or vias under the coil (p. 7) "
        "(https://datasheet.lcsc.com/datasheet/pdf/b8f89bf2cd49b99b92d10b430994df40.pdf?productCode=C668312)",
        "inductor Murata DFE201612E", (-1.0, -0.8, 1.0, 0.8), dfe201612e(), pin1=False,
        model_offset=(0.0, 0.0, 0.6), model_scale=(1.0, 1.0, 1.2),  # EasyEDA's model is 1.0 tall, centred
        keepout=(-0.4, -0.8, 0.4, 0.8)),
}

# Stock footprints copied with their 0.2 mm thermal-via drills opened to 0.3 mm.
STOCK_COPIES = {"ESP32-S3-WROOM-1_Drill0.3": "RF_Module.pretty/ESP32-S3-WROOM-1.kicad_mod"}

SILK_W = 0.15  # JLCPCB's minimum silkscreen line
FAB_W = 0.1
CRTYD_W = 0.05
CRTYD_GAP = 0.25  # courtyard beyond the pads and the body (KiCad library rule)
SILK_PAD_GAP = 0.2  # silkscreen line edge to copper

# --------------------------------------------------------------------------------------------
# S-expression writing (kicad-cli then rewrites the files in KiCad's own layout).
# --------------------------------------------------------------------------------------------


def num(v: float) -> str:
    s = f"{round(v, 6):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sexpr(node, indent: int = 0) -> str:
    """KiCad style: a list of atoms on one line, a list holding lists one child per line."""
    if not isinstance(node, list):
        return node
    pad = "\t" * indent
    if not any(isinstance(c, list) for c in node):
        return pad + "(" + " ".join(node) + ")"
    first = next(i for i, c in enumerate(node) if isinstance(c, list))
    if not all(isinstance(c, list) for c in node[first:]):
        raise ValueError(f"atom after a list in {node[0]}")
    lines = [pad + "(" + " ".join(node[:first])] + [sexpr(c, indent + 1) for c in node[first:]]
    return "\n".join(lines) + "\n" + pad + ")"


def xy(tag: str, x: float, y: float) -> list:
    return [tag, num(x), num(y)]


def font(size: float, thickness: float | None = None) -> list:
    f = ["font", ["size", num(size), num(size)]]
    if thickness is not None:
        f.append(["thickness", num(thickness)])
    return ["effects", f]


# --------------------------------------------------------------------------------------------
# Symbols
# --------------------------------------------------------------------------------------------

GRID = 2.54
CHAR = 1.25  # advance of a 1.27 mm KiCad stroke-font character, a little generous


def text_len(name: str) -> float:
    return len(re.sub(r"~\{([^}]*)\}", r"\1", name)) * CHAR


def ceil_grid(v: float) -> float:
    return math.ceil(v / GRID - 1e-9) * GRID


def symbol(name: str, part: Part) -> list:
    sides = {s: getattr(part, s) for s in ("left", "right", "top", "bottom")}
    placed = [n for s in sides.values() for n in s]
    if sorted(placed, key=int) != sorted(part.pins, key=int):
        raise SystemExit(f"{name}: the layout does not place every pin exactly once")
    names = {s: [part.pins[n][0] for n in sides[s]] for s in sides}
    longest = {s: max((text_len(t) for t in names[s]), default=0.0) for s in sides}
    rows = max(len(sides["left"]), len(sides["right"]), 1)
    cols = max(len(sides["top"]), len(sides["bottom"]), 1)
    row_y = [GRID * (math.ceil((rows - 1) / 2) - i) for i in range(rows)]
    col_x = [GRID * (i - (cols - 1) // 2) for i in range(cols)]
    # Wide enough that the vertical top and bottom names clear the horizontal side names, and that
    # the reference (top left) and the value (top right) do not run into each other.
    half_w = ceil_grid(max(0.508 + max(longest["left"], longest["right"]) + 0.8 + max(abs(x) for x in col_x),
                           (longest["left"] + longest["right"]) / 2 + 2.0,
                           (text_len("U?") + text_len(name)) / 2 + 0.6, 5.08))
    # Tall enough for the side rows, and for the top and bottom names that share a column.
    column_need = [text_len(names["top"][i]) if i < len(names["top"]) else 0.0 for i in range(cols)]
    column_need = [c + (text_len(names["bottom"][i]) if i < len(names["bottom"]) else 0.0) for i, c in
                   enumerate(column_need)]
    half_h = ceil_grid(max(max(abs(y) for y in row_y) + GRID, max(column_need) / 2 + 0.508 + 0.6))

    def pin(n: str, x: float, y: float, angle: int) -> list:
        pname, ptype = part.pins[n]
        return ["pin", ptype, "line", ["at", num(x), num(y), str(angle)], ["length", num(GRID)],
                ["name", q(pname), font(1.27)], ["number", q(n), font(1.27)]]

    pins = []
    for i, n in enumerate(sides["left"]):
        pins.append(pin(n, -half_w - GRID, row_y[i], 0))
    for i, n in enumerate(sides["right"]):
        pins.append(pin(n, half_w + GRID, row_y[i], 180))
    for i, n in enumerate(sides["top"]):
        pins.append(pin(n, col_x[i], half_h + GRID, 270))
    for i, n in enumerate(sides["bottom"]):
        pins.append(pin(n, col_x[i], -half_h - GRID, 90))

    def prop(key: str, value: str, x: float, y: float, hide: bool, justify: str | None = None) -> list:
        p = ["property", q(key), q(value), ["at", num(x), num(y), "0"]]
        if hide:
            p.append(["hide", "yes"])
        eff = font(1.27)
        if justify:
            eff.append(["justify", justify])
        return p + [eff]

    top_y = half_h + (GRID if sides["top"] else 0.0) + 1.27  # fields above any top pins
    return ["symbol", q(name), ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            prop("Reference", "U", -half_w, top_y, False, "left"),
            prop("Value", name, half_w, top_y, False, "right"),
            prop("Footprint", part.footprint, 0, -half_h - GRID - 2.54, True),
            prop("Datasheet", part.datasheet, 0, -half_h - GRID - 5.08, True),
            prop("Description", part.description, 0, -half_h - GRID - 7.62, True),
            prop("ki_keywords", f"{part.keywords} {part.lcsc}", 0, 0, True),
            ["symbol", q(f"{name}_0_1"),
             ["rectangle", xy("start", -half_w, half_h), xy("end", half_w, -half_h),
              ["stroke", ["width", "0.254"], ["type", "default"]], ["fill", ["type", "background"]]]],
            ["symbol", q(f"{name}_1_1"), *pins]]


def symbol_library() -> str:
    lib = ["kicad_symbol_lib", ["version", "20251024"], ["generator", q("kicad_symbol_editor")],
           ["generator_version", q("10.0")]]
    lib += [symbol(name, PARTS[name]) for name in sorted(PARTS)]
    return sexpr(lib) + "\n"


# --------------------------------------------------------------------------------------------
# Footprints
# --------------------------------------------------------------------------------------------


def paste_margin(size: tuple[float, float], aperture: tuple[float, float]) -> tuple[float, float]:
    """KiCad shrinks each side of a paste opening by margin + ratio * pad size; solve both axes."""
    (w, h), (aw, ah) = size, aperture
    dw, dh = (aw - w) / 2, (ah - h) / 2
    if abs(w - h) < 1e-9:
        return dw, 0.0
    ratio = (dw - dh) / (w - h)
    return dw - ratio * w, ratio


def pad_bbox(p: Pad, grow: float = 0.0) -> tuple[float, float, float, float]:
    return p.x - p.w / 2 - grow, p.y - p.h / 2 - grow, p.x + p.w / 2 + grow, p.y + p.h / 2 + grow


def union(boxes) -> tuple[float, float, float, float]:
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def round_out(box, step: float = 0.01) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = box
    return (math.floor(x0 / step + 1e-6) * step, math.floor(y0 / step + 1e-6) * step,
            math.ceil(x1 / step - 1e-6) * step, math.ceil(y1 / step - 1e-6) * step)


def clip_segment(a: tuple[float, float], b: tuple[float, float], boxes) -> list:
    """Parts of the axis-aligned segment a-b that stay out of every box."""
    (ax, ay), (bx, by) = a, b
    horizontal = abs(ay - by) < 1e-9
    lo, hi = (min(ax, bx), max(ax, bx)) if horizontal else (min(ay, by), max(ay, by))
    fixed = ay if horizontal else ax
    cuts = []
    for x0, y0, x1, y1 in boxes:
        if horizontal and y0 < fixed < y1:
            cuts.append((x0, x1))
        if not horizontal and x0 < fixed < x1:
            cuts.append((y0, y1))
    pieces, start = [], lo
    for c0, c1 in sorted(cuts):
        if c0 > start:
            pieces.append((start, min(c0, hi)))
        start = max(start, c1)
    if start < hi:
        pieces.append((start, hi))
    out = []
    for s, e in pieces:
        if e - s >= 0.2:
            out.append(((s, fixed), (e, fixed)) if horizontal else ((fixed, s), (fixed, e)))
    return out


def footprint(name: str, fp: Footprint) -> str:
    ids = (str(uuid.uuid5(UUID_NS, f"{name}/{i}")) for i in range(1000))
    items: list = []

    def line(a, b, layer: str, width: float) -> None:
        items.append(["fp_line", xy("start", *a), xy("end", *b), ["stroke", ["width", num(width)], ["type", "solid"]],
                      ["layer", q(layer)], ["uuid", q(next(ids))]])

    def circle(c, r: float, layer: str, width: float, fill: bool = False) -> None:
        items.append(["fp_circle", xy("center", *c), xy("end", c[0] + r, c[1]),
                      ["stroke", ["width", num(width)], ["type", "solid"]], ["fill", "yes" if fill else "no"],
                      ["layer", q(layer)], ["uuid", q(next(ids))]])

    def rect(box, layer: str, width: float) -> None:
        items.append(["fp_rect", xy("start", box[0], box[1]), xy("end", box[2], box[3]),
                      ["stroke", ["width", num(width)], ["type", "solid"]], ["fill", "no"],
                      ["layer", q(layer)], ["uuid", q(next(ids))]])

    bx0, by0, bx1, by1 = fp.body
    copper = [p for p in fp.pads if p.copper]
    keep = [pad_bbox(p, SILK_PAD_GAP + SILK_W / 2) for p in copper]

    # Fab: package outline with a chamfered pin 1 corner (round bodies get a circle).
    if fp.round_body:
        circle(((bx0 + bx1) / 2, (by0 + by1) / 2), (bx1 - bx0) / 2, "F.Fab", FAB_W)
    else:
        one = next((p for p in fp.pads if p.number == "1"), None) if fp.pin1 else None
        corners = [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)]
        chamfer = min(1.0, 0.25 * min(bx1 - bx0, by1 - by0))
        cut = None
        if one is not None:
            cut = min(range(4), key=lambda i: (corners[i][0] - one.x) ** 2 + (corners[i][1] - one.y) ** 2)
        pts = []
        for i, (cx, cy) in enumerate(corners):
            if i == cut:
                px, py = corners[i - 1]
                nx, ny = corners[(i + 1) % 4]
                pts.append((cx + math.copysign(chamfer, px - cx) if px != cx else cx,
                            cy + math.copysign(chamfer, py - cy) if py != cy else cy))
                pts.append((cx + math.copysign(chamfer, nx - cx) if nx != cx else cx,
                            cy + math.copysign(chamfer, ny - cy) if ny != cy else cy))
            else:
                pts.append((cx, cy))
        for a, b in zip(pts, pts[1:] + pts[:1]):
            line(a, b, "F.Fab", FAB_W)

    # Silkscreen: the outline 0.1 mm outside the body, kept clear of the copper, and a pin 1 dot.
    silk_items = []
    if not fp.round_body:
        s = 0.1 + SILK_W / 2
        sx0, sy0, sx1, sy1 = bx0 - s, by0 - s, bx1 + s, by1 + s
        for a, b in (((sx0, sy0), (sx1, sy0)), ((sx1, sy0), (sx1, sy1)), ((sx1, sy1), (sx0, sy1)), ((sx0, sy1), (sx0, sy0))):
            for seg in clip_segment(a, b, keep):
                line(*seg, "F.SilkS", SILK_W)
                silk_items.append((min(seg[0][0], seg[1][0]) - SILK_W / 2, min(seg[0][1], seg[1][1]) - SILK_W / 2,
                                   max(seg[0][0], seg[1][0]) + SILK_W / 2, max(seg[0][1], seg[1][1]) + SILK_W / 2))
    if fp.pin1:
        one = next(p for p in fp.pads if p.number == "1")
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        r = 0.1
        if one.w >= one.h:  # pad long in X: the dot sits beyond its outer end
            step = ((one.x - cx) / abs(one.x - cx), 0.0)
            reach = one.w / 2 + SILK_PAD_GAP + r + SILK_W / 2
        else:
            step = (0.0, (one.y - cy) / abs(one.y - cy))
            reach = one.h / 2 + SILK_PAD_GAP + r + SILK_W / 2
        dot = (one.x + step[0] * reach, one.y + step[1] * reach)
        clear = r + SILK_W + 0.15  # dot edge to an outline edge
        while any(x0 - clear < dot[0] < x1 + clear and y0 - clear < dot[1] < y1 + clear
                  for x0, y0, x1, y1 in silk_items):
            dot = (dot[0] + step[0] * 0.05, dot[1] + step[1] * 0.05)
        circle(dot, r, "F.SilkS", SILK_W, fill=True)
        silk_items.append((dot[0] - r - SILK_W / 2, dot[1] - r - SILK_W / 2, dot[0] + r + SILK_W / 2, dot[1] + r + SILK_W / 2))

    # Courtyard: pads and body plus 0.25 mm, and the silkscreen.
    crt = round_out(union([*(pad_bbox(p, CRTYD_GAP) for p in copper), (bx0 - CRTYD_GAP, by0 - CRTYD_GAP,
                                                                         bx1 + CRTYD_GAP, by1 + CRTYD_GAP),
                           *silk_items]))
    if fp.round_body:
        circle(((bx0 + bx1) / 2, (by0 + by1) / 2), max(crt[2], -crt[0]), "F.CrtYd", CRTYD_W)
    else:
        rect(crt, "F.CrtYd", CRTYD_W)

    if fp.fpc_arrow:  # where the FPC goes in
        tip = (0.0, by1 + 0.3)
        line((0.0, by1 + 1.8), tip, "F.Fab", FAB_W)
        line(tip, (-0.4, tip[1] + 0.5), "F.Fab", FAB_W)
        line(tip, (0.4, tip[1] + 0.5), "F.Fab", FAB_W)

    fab_size = 0.5 if bx1 - bx0 < 3 else 1.0
    head = ["footprint", q(name), ["version", "20260206"], ["generator", q("pcbnew")], ["generator_version", q("10.0")],
            ["layer", q("F.Cu")], ["descr", q(fp.descr)], ["tags", q(fp.tags + " " + fp.lcsc)]]
    head.append(["property", q("Reference"), q("REF**"), ["at", "0", num(crt[1] - 0.7), "0"], ["layer", q("F.SilkS")],
                 ["uuid", q(next(ids))], font(1.0, 0.15)])
    head.append(["property", q("Value"), q(name), ["at", "0", num(crt[3] + 0.7), "0"], ["layer", q("F.Fab")],
                 ["uuid", q(next(ids))], font(1.0, 0.15)])
    datasheet = re.search(r"\((https?://[^)]+)\)", fp.descr)
    head.append(["property", q("Datasheet"), q(datasheet.group(1) if datasheet else ""), ["at", "0", "0", "0"],
                 ["layer", q("F.Fab")], ["hide", "yes"], ["uuid", q(next(ids))], font(1.27)])
    head.append(["property", q("Description"), q(re.sub(r" \(https?://[^)]+\)", "", fp.descr)), ["at", "0", "0", "0"],
                 ["layer", q("F.Fab")], ["hide", "yes"], ["uuid", q(next(ids))], font(1.27)])
    head.append(["attr", "smd"])
    head.append(["duplicate_pad_numbers_are_jumpers", "no"])
    head += items
    head.append(["fp_text", "user", q("${REFERENCE}"), ["at", "0", "0", "0"], ["layer", q("F.Fab")],
                 ["uuid", q(next(ids))], font(fab_size, round(fab_size * 0.15, 3))])

    for p in fp.pads:
        layers = ["layers", q("*.Cu"), q("*.Mask")] if p.kind == "thru_hole" else ["layers", *map(q, p.layers)]
        node = ["pad", q(p.number), p.kind, p.shape, ["at", num(p.x), num(p.y)], ["size", num(p.w), num(p.h)]]
        if p.kind == "thru_hole":
            node.append(["drill", num(p.drill)])
        if p.exposed:
            node.append(["property", "pad_prop_heatsink"])
        node.append(layers)
        if p.kind == "thru_hole":
            node.append(["remove_unused_layers", "no"])
        if p.shape == "roundrect":
            node.append(["roundrect_rratio", num(p.rratio)])
        if p.paste:
            margin, ratio = paste_margin((p.w, p.h), p.paste)
            node.append(["solder_paste_margin", num(margin)])
            if ratio:
                node.append(["solder_paste_margin_ratio", num(ratio)])
        if p.exposed:
            node.append(["zone_connect", "2"])
        if p.ring:
            radius, width = p.ring
            node.append(["options", ["clearance", "outline"], ["anchor", "circle"]])
            node.append(["primitives", ["gr_circle", xy("center", -p.x, -p.y), xy("end", -p.x + radius, -p.y),
                                        ["width", num(width)], ["fill", "no"]]])
        node.append(["uuid", q(next(ids))])
        head.append(node)

    if fp.keepout:
        x0, y0, x1, y1 = fp.keepout
        head.append(["zone", ["net", "0"], ["net_name", q("")], ["layers", q("F.Cu")], ["uuid", q(next(ids))],
                     ["name", q("no copper under the coil")], ["hatch", "edge", "0.5"],
                     ["connect_pads", ["clearance", "0"]], ["min_thickness", "0.25"],
                     ["filled_areas_thickness", "no"],
                     ["keepout", ["tracks", "not_allowed"], ["vias", "not_allowed"], ["pads", "allowed"],
                      ["copperpour", "not_allowed"], ["footprints", "allowed"]],
                     ["placement", ["enabled", "no"], ["sheetname", q("")]],
                     ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
                     ["polygon", ["pts", xy("xy", x0, y0), xy("xy", x1, y0), xy("xy", x1, y1), xy("xy", x0, y1)]]])

    head.append(["embedded_fonts", "no"])
    head.append(["model", q(f"{MODEL_PATH}/{name}.step"), ["offset", ["xyz", *map(num, fp.model_offset)]],
                 ["scale", ["xyz", *map(num, fp.model_scale)]], ["rotate", ["xyz", *map(num, fp.model_rotate)]]])
    return sexpr(head) + "\n"


def stock_copy(name: str, rel: str, stock_dir: Path) -> str:
    text = (stock_dir / rel).read_text()
    if text.count("(drill 0.2)") != 12:
        raise SystemExit(f"{rel}: expected 12 thermal vias drilled 0.2 mm")
    text = re.sub(r'\(footprint "[^"]+"', f'(footprint "{name}"', text, count=1)
    text = text.replace('(descr "', '(descr "Thermal vias opened from 0.2 to 0.3 mm (JLCPCB no-fee drill). ', 1)
    return text.replace("(drill 0.2)", "(drill 0.3)")


# --------------------------------------------------------------------------------------------
# EasyEDA cross-check
# --------------------------------------------------------------------------------------------


def norm(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper().replace("~{", "").replace("}", ""))


def easyeda_pins(sym_text: str) -> dict[str, dict[str, str]]:
    out = {}
    starts = [m.start() for m in re.finditer(r'\n\t\(symbol "', sym_text)] + [len(sym_text)]
    for a, b in zip(starts, starts[1:]):
        block = sym_text[a:b]
        name = re.match(r'\n\t\(symbol "([^"]+)"', block).group(1)
        out[name] = {n: nm for nm, n in re.findall(r'\(pin \w+ \w+.*?\(name "([^"]*)".*?\(number "([^"]*)"', block, re.S)}
    return out


def read_pads(text: str) -> list[tuple[str, float, float, float, float]]:
    out = []
    for m in re.finditer(r'\(pad "([^"]*)" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\s*\(size ([\d.]+) ([\d.]+)\)',
                         text):
        n, x, y, rot, w, h = m.groups()
        w, h = float(w), float(h)
        if round(float(rot or 0)) % 180 == 90:
            w, h = h, w
        out.append((n, float(x), float(y), w, h))
    return out


def compare_with_easyeda(src: Path) -> None:
    sym = src / "symbol" / "owltunes.kicad_sym"
    if sym.is_file():
        theirs = easyeda_pins(sym.read_text())
        for name, part in PARTS.items():
            got = theirs.get(name, {})
            diff = [f"{n}: {got.get(n)!r} vs {pn!r}" for n, (pn, _) in part.pins.items() if norm(got.get(n, "")) != norm(pn)]
            print(f"  {name}: EasyEDA pin names {'agree' if not diff else 'differ: ' + '; '.join(diff)}")
    for name, fp in FOOTPRINTS.items():
        path = src / "owltunes.pretty" / f"{fp.easyeda}.kicad_mod"
        if not path.is_file():
            print(f"  {name}: no EasyEDA footprint {fp.easyeda}")
            continue
        theirs = read_pads(path.read_text())
        mine = [(p.number, p.x, p.y, p.w, p.h) for p in fp.pads if p.copper]
        if fp.easyeda.startswith("CONN-SMD_FH26W"):
            theirs = [(("MP" if n.startswith("G") else n), *rest) for n, *rest in theirs]
        if sorted(t[0] for t in theirs) != sorted(m[0] for m in mine):
            print(f"  {name}: EasyEDA pads {sorted(t[0] for t in theirs)} differ in number")
            continue
        worst, where = 0.0, ""
        for m in mine:
            t = min((t for t in theirs if t[0] == m[0]), key=lambda t: sum(abs(a - b) for a, b in zip(t[1:], m[1:])))
            d = max(abs(a - b) for a, b in zip(t[1:], m[1:]))
            if d > worst:
                worst, where = d, f"pad {m[0]} EasyEDA {t[1:]} datasheet {m[1:]}"
        print(f"  {name}: EasyEDA differs from the datasheet by up to {worst:.3f} mm" + (f" ({where})" if where else ""))


# --------------------------------------------------------------------------------------------


def kicad_cli(*args: str) -> None:
    run = subprocess.run(["kicad-cli", *args], capture_output=True, text=True)
    if run.returncode:
        sys.stderr.write(run.stdout + run.stderr)
        raise SystemExit(f"kicad-cli {' '.join(args)} failed with exit code {run.returncode}")


def build(lib: Path, src: Path | None, stock_dir: Path) -> None:
    (lib / "owltunes.pretty").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "owltunes.kicad_sym").write_text(symbol_library())
        kicad_cli("sym", "upgrade", "--force", str(tmp / "owltunes.kicad_sym"))
        shutil.copy(tmp / "owltunes.kicad_sym", lib / "owltunes.kicad_sym")
        (tmp / "fp.pretty").mkdir()
        for name, fp in FOOTPRINTS.items():
            (tmp / "fp.pretty" / f"{name}.kicad_mod").write_text(footprint(name, fp))
        kicad_cli("fp", "upgrade", "--force", str(tmp / "fp.pretty"))
        for name in FOOTPRINTS:
            shutil.copy(tmp / "fp.pretty" / f"{name}.kicad_mod", lib / "owltunes.pretty" / f"{name}.kicad_mod")
    for name, rel in STOCK_COPIES.items():
        (lib / "owltunes.pretty" / f"{name}.kicad_mod").write_text(stock_copy(name, rel, stock_dir))
    if src is not None:
        models = lib / "3dmodels"
        models.mkdir(exist_ok=True)
        for name, fp in FOOTPRINTS.items():
            step = next(src.rglob(f"{fp.easyeda}.step"), None)
            if step is None:
                print(f"  {name}: no EasyEDA STEP model")
                continue
            shutil.copy(step, models / f"{name}.step")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from", dest="src", type=Path, help="JLC2KiCadLib output to use instead of downloading")
    ap.add_argument("--offline", action="store_true", help="no download, no 3D models, no EasyEDA comparison")
    ap.add_argument("--lib", type=Path, default=LIB, help="library directory to write (default hardware/lib)")
    ap.add_argument("--stock", type=Path, default=STOCK_FOOTPRINTS, help="KiCad footprint library")
    args = ap.parse_args(argv)
    src = None
    if not args.offline:
        src = args.src or ROOT / "build" / "jlclib"
        if args.src is None:
            shutil.rmtree(src, ignore_errors=True)
            lcsc = sorted({p.lcsc for p in PARTS.values()} | {f.lcsc for f in FOOTPRINTS.values()})
            subprocess.run(["JLC2KiCadLib", *lcsc, "-dir", str(src), "-symbol_lib", "owltunes",
                            "-footprint_lib", "owltunes.pretty", "-models", "STEP"], check=True)
        kicad_cli("sym", "upgrade", "--force", str(src / "symbol" / "owltunes.kicad_sym"))
        kicad_cli("fp", "upgrade", "--force", str(src / "owltunes.pretty"))
        print("EasyEDA cross-check:")
        compare_with_easyeda(src)
    build(args.lib, src, args.stock)
    print(f"{args.lib.relative_to(ROOT) if args.lib.is_relative_to(ROOT) else args.lib}: {len(PARTS)} symbols, "
          f"{len(FOOTPRINTS) + len(STOCK_COPIES)} footprints" + ("" if src is None else ", 3D models"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
