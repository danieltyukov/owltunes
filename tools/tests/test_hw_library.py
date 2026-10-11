"""hardware/lib must match the datasheets: pin numbers, names, electrical types, pads, models.

The expected tables are typed from the datasheets, not from tools/hw/hw_lib_build.py, so a
mistake in the build script's tables fails here. Land patterns are written the way each
datasheet dimensions them (pitch, row spacing, pad size) and measured in the .kicad_mod files.
Footprint coordinates are KiCad's: millimetres, X right, Y down, seen from the top.
"""

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB = ROOT / "hardware" / "lib"
STOCK = pathlib.Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))

# number: (name, type). Sources: TPS63802 SLVSEU9D table 7-1 (p. 4); MAX17048 19-6171 rev 7
# pin description (p. 6); TMAG5273 SLYS045C table 4-1 (p. 4); LIS2DW12 DS11811 rev 9 table 1
# (p. 4); OPT3001 SBOS681C pin functions (p. 3) and DNP0006A (p. 41, thermal pad).
DATASHEET = {
    "TPS63802DLAR": {"1": ("EN", "input"), "2": ("MODE", "input"), "3": ("AGND", "power_in"),
                     "4": ("FB", "input"), "5": ("PG", "open_collector"), "6": ("VOUT", "power_out"),
                     "7": ("L2", "passive"), "8": ("GND", "power_in"), "9": ("L1", "passive"),
                     "10": ("VIN", "power_in")},
    "MAX17048G+T10": {"1": ("CTG", "input"), "2": ("CELL", "input"), "3": ("VDD", "power_in"),
                      "4": ("GND", "power_in"), "5": ("ALRT", "open_collector"), "6": ("QSTRT", "input"),
                      "7": ("SCL", "input"), "8": ("SDA", "bidirectional"), "9": ("EP", "passive")},
    "TMAG5273A2QDBVR": {"1": ("SCL", "input"), "2": ("GND", "power_in"), "3": ("GNDTEST", "passive"),
                        "4": ("VCC", "power_in"), "5": ("INT", "open_collector"), "6": ("SDA", "bidirectional")},
    "LIS2DW12TR": {"1": ("SCLSPC", "input"), "2": ("CS", "input"), "3": ("SDOSA0", "bidirectional"),
                   "4": ("SDASDISDO", "bidirectional"), "5": ("NC", "no_connect"), "6": ("GND", "power_in"),
                   "7": ("RES", "passive"), "8": ("GND", "power_in"), "9": ("VDD", "power_in"),
                   "10": ("VDDIO", "power_in"), "11": ("INT2", "output"), "12": ("INT1", "output")},
    "OPT3001DNPR": {"1": ("VDD", "power_in"), "2": ("ADDR", "input"), "3": ("GND", "power_in"),
                    "4": ("SCL", "input"), "5": ("INT", "open_collector"), "6": ("SDA", "bidirectional"),
                    "7": ("EP", "passive")},
}
PADS = {
    "TI_DLA_VSON-10_2x3mm_P0.5mm": {str(n) for n in range(1, 11)},
    "Maxim_TDFN-8-1EP_2x2mm_P0.5mm": {str(n) for n in range(1, 10)},
    "TI_DNP_USON-6-1EP_2x2mm_P0.65mm": {str(n) for n in range(1, 8)},
    "Hirose_FH26W-31S-0.3SHW_1x31-1MP_P0.30mm_Horizontal": {str(n) for n in range(1, 32)} | {"MP"},
    "PogoPin_Xinyangze_YZ71215080P-02": {"1"},
    "L_Murata_DFE201612E": {"1", "2"},
}


def dla0010a() -> list:
    """TPS63802 SLVSEU9D p. 36: 0.5 pitch, pins 1-5 0.6 x 0.25 at x -0.9, pin 1 at the top;
    pins 6, 7, 9, 10 0.9 x 0.25 at x 0.75; pin 8 (GND) 1.3 x 0.25 at x 0.55."""
    pads = [(str(1 + i), -0.9, -1.0 + 0.5 * i, 0.6, 0.25) for i in range(5)]
    pads += [(str(n), 0.75, y, 0.9, 0.25) for n, y in ((6, 1.0), (7, 0.5), (9, -0.5), (10, -1.0))]
    return pads + [("8", 0.55, 0.0, 1.3, 0.25)]


def maxim_90_0065() -> list:
    """Maxim land pattern 90-0065 rev E (8L TDFN 2 x 2): pads 0.30 x 0.70 on 0.50 pitch, row
    centres 1.98 apart, exposed pad 0.80 x 1.38. Drawn as in the MAX17048 top view (p. 6): pins
    1-4 along the bottom from the left, 5-8 along the top from the right."""
    pads = [(str(1 + i), -0.75 + 0.5 * i, 0.99, 0.30, 0.70) for i in range(4)]
    pads += [(str(5 + i), 0.75 - 0.5 * i, -0.99, 0.30, 0.70) for i in range(4)]
    return pads + [("9", 0.0, 0.0, 1.38, 0.80)]


def dnp0006a() -> list:
    """OPT3001 SBOS681C p. 42: pads 0.5 x 0.25 on 0.65 pitch, row centres 1.9 apart, thermal pad
    0.65 x 1.35. Turned so pins 1-3 run along the bottom from the left (the EasyEDA/JLC zero
    orientation), so the pads are 0.25 wide in X."""
    pads = [(str(1 + i), -0.65 + 0.65 * i, 0.95, 0.25, 0.5) for i in range(3)]
    pads += [(str(4 + i), 0.65 - 0.65 * i, -0.95, 0.25, 0.5) for i in range(3)]
    return pads + [("7", 0.0, 0.0, 1.35, 0.65)]


def fh26w(n: int = 31) -> list:
    """Hirose FH26W catalogue EDC3-323714-05 p. 1 (recommended PCB mounting pattern) and p. 4
    (31 contacts: B 8.4, C 9.0): contacts 0.3 wide on 0.3 pitch overall; odd contacts (FPC
    side, contact 1 on the left) 0.8 long, even contacts 0.65 long, 2.15 between the rows, 3.6
    overall; fitting tabs 0.4 x 0.95, 0.5 beyond the outer odd contacts and 0.2 in from the odd
    row's outer edge. The origin is midway between the row centres."""
    odd_y = (0.65 / 2 + 2.15 + 0.8 / 2) / 2  # row centres 2.875 apart: odd row 1.4375 below the origin
    pads = [(str(k), (k - (n + 1) / 2) * 0.3, odd_y if k % 2 else -odd_y, 0.3, 0.8 if k % 2 else 0.65)
            for k in range(1, n + 1)]
    tab_x = (n - 1) / 2 * 0.3 + 0.5 + 0.4 / 2
    tab_y = odd_y + 0.8 / 2 - 0.2 - 0.95 / 2
    return pads + [("MP", -tab_x, tab_y, 0.4, 0.95), ("MP", tab_x, tab_y, 0.4, 0.95)]


def dfe201612e() -> list:
    """Murata DFE201612E reference specification J(E)TE243A-0006B-01 p. 5: 2.4 overall, 0.8
    between the pads, 1.8 tall."""
    return [("1", -0.8, 0.0, 0.8, 1.8), ("2", 0.8, 0.0, 0.8, 1.8)]


# Pogo pin YZ71215080P-02 (LCSC C5157364 drawing p. 3): flange 2.00, locating post 0.60 +-0.03 by
# 1.00. No land pattern is published: a 2.2 mm pad (flange plus 0.1 mm) and a plated 0.8 mm hole
# for the post (0.63 mm post in the smallest JLC plated hole, 0.72 mm).
LANDS = {
    "TI_DLA_VSON-10_2x3mm_P0.5mm": dla0010a(),
    "Maxim_TDFN-8-1EP_2x2mm_P0.5mm": maxim_90_0065(),
    "TI_DNP_USON-6-1EP_2x2mm_P0.65mm": dnp0006a(),
    "Hirose_FH26W-31S-0.3SHW_1x31-1MP_P0.30mm_Horizontal": fh26w(),
    "PogoPin_Xinyangze_YZ71215080P-02": [("1", 0.0, 0.0, 2.2, 2.2), ("1", 0.0, 0.0, 1.1, 1.1)],
    "L_Murata_DFE201612E": dfe201612e(),
}
POGO_DRILL = 0.8

# Stock KiCad footprints the boards use, against the manufacturers' land patterns: EVQP7A
# (Panasonic EVQP7 catalogue p. 2: 5.0 and 2.2 across, 2.5 and 0.4 down); TS-1088 (XUNPU drawing
# for C720477: 5.50 and 3.40 across, 2.00 tall); LGA-12 (LIS2DW12 DS11811 rev 9 p. 56 terminals
# 0.275 x 0.25 inset 0.1 on 0.5 pitch, ST TN0018 rev 8 p. 12: land = terminal + 0.1 mm).
STOCK_LANDS = {
    "Button_Switch_SMD.pretty/SW_SPST_EVQP7A": [(n, sx * 1.8, sy * 0.725, 1.4, 1.05)
                                                for n, sy in (("1", -1), ("2", 1)) for sx in (-1, 1)],
    "Button_Switch_SMD.pretty/SW_SPST_TS-1088-xR020": [("1", -2.225, 0.0, 1.05, 2.0), ("2", 2.225, 0.0, 1.05, 2.0)],
    "Package_LGA.pretty/LGA-12_2x2mm_P0.5mm": (
        [(str(1 + i), -0.7625, -0.75 + 0.5 * i, 0.375, 0.35) for i in range(4)]
        + [("5", -0.25, 0.7625, 0.35, 0.375), ("6", 0.25, 0.7625, 0.35, 0.375)]
        + [(str(7 + i), 0.7625, 0.75 - 0.5 * i, 0.375, 0.35) for i in range(4)]
        + [("11", 0.25, -0.7625, 0.35, 0.375), ("12", -0.25, -0.7625, 0.35, 0.375)]),
}


def norm(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper().replace("~{", "").replace("}", ""))


def symbols(text: str) -> dict[str, dict[str, tuple[str, str]]]:
    out = {}
    starts = [m.start() for m in re.finditer(r'\n\t\(symbol "', text)] + [len(text)]
    for a, b in zip(starts, starts[1:]):
        block = text[a:b]
        name = re.match(r'\n\t\(symbol "([^"]+)"', block).group(1)
        pins = re.findall(r'\(pin (\w+) \w+.*?\(name "([^"]*)".*?\(number "([^"]*)"', block, re.S)
        out[name] = {num: (norm(n), t) for t, n, num in pins}
    return out


def pads(text: str) -> list[dict]:
    """Every pad of a .kicad_mod: number, kind, centre, size as placed (rotation applied), drill."""
    out = []
    for m in re.finditer(r'\(pad "([^"]*)" (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)'
                         r'\s*\(size ([\d.]+) ([\d.]+)\)(.*?)\(layers ([^)]*)\)', text, re.S):
        num, kind, shape, x, y, rot, w, h, rest, layers = m.groups()
        w, h = float(w), float(h)
        if round(float(rot or 0)) % 180 == 90:
            w, h = h, w
        drill = re.search(r"\(drill (?:oval )?([\d.]+)", rest)
        out.append({"number": num, "kind": kind, "shape": shape, "x": float(x), "y": float(y), "w": w, "h": h,
                    "drill": float(drill.group(1)) if drill else None, "layers": layers})
    return out


def paste_apertures(text: str) -> dict[str, tuple[float, float]]:
    """Stencil opening of every pad with a local paste margin: size + 2 (margin + ratio * size)."""
    out = {}
    for m in re.finditer(r'\(pad "([^"]*)" \w+ \w+\s*\(at [-\d. ]+\)\s*\(size ([\d.]+) ([\d.]+)\)'
                         r'((?:(?!\(pad ).)*)', text, re.S):
        num, w, h, rest = m.group(1), float(m.group(2)), float(m.group(3)), m.group(4)
        margin = re.search(r"\(solder_paste_margin ([-\d.]+)\)", rest)
        ratio = re.search(r"\(solder_paste_margin_ratio ([-\d.]+)\)", rest)
        if margin or ratio:
            mg = float(margin.group(1)) if margin else 0.0
            r = float(ratio.group(1)) if ratio else 0.0
            out[num] = (w + 2 * (mg + r * w), h + 2 * (mg + r * h))
    return out


def courtyard(text: str) -> tuple[float, float, float, float]:
    """Bounding box of the F.CrtYd lines, rectangles and circles."""
    xs, ys = [], []
    item = r'\((fp_line|fp_rect|fp_circle)\s*((?:(?!\(fp_|\(pad ).)*?)\(layer "F\.CrtYd"\)'
    for kind, body in re.findall(item, text, re.S):
        if kind == "fp_circle":
            cx, cy = map(float, re.search(r"\(center ([-\d.]+) ([-\d.]+)\)", body).groups())
            ex, ey = map(float, re.search(r"\(end ([-\d.]+) ([-\d.]+)\)", body).groups())
            r = ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5
            xs += [cx - r, cx + r]
            ys += [cy - r, cy + r]
        else:
            a, b, c, d = map(float, re.search(r"\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)",
                                              body).groups())
            xs += [a, c]
            ys += [b, d]
    return min(xs), min(ys), max(xs), max(ys)


def land_matches(test: unittest.TestCase, name: str, have: list[dict], want: list, tol: float = 0.005) -> None:
    """Every expected pad is in the file once, within tol mm; nothing else is."""
    got = sorted((p["number"], round(p["x"], 3), round(p["y"], 3), round(p["w"], 3), round(p["h"], 3))
                 for p in have)
    exp = sorted((n, round(x, 3), round(y, 3), round(w, 3), round(h, 3)) for n, x, y, w, h in want)
    test.assertEqual(len(got), len(exp), f"{name}: pad count")
    for g, e in zip(got, exp):
        test.assertEqual(g[0], e[0], name)
        for a, b in zip(g[1:], e[1:]):
            test.assertAlmostEqual(a, b, delta=tol, msg=f"{name} pad {g[0]}: {g[1:]} != {e[1:]}")


class LibraryTest(unittest.TestCase):
    def test_symbol_pins_match_the_datasheets(self):
        have = symbols((LIB / "owltunes.kicad_sym").read_text())
        self.assertEqual(sorted(have), sorted(DATASHEET))
        for name, pins in DATASHEET.items():
            self.assertEqual(have[name], pins, name)

    def test_footprints_have_the_right_pads_courtyard_and_model(self):
        for name, pads_ in PADS.items():
            text = (LIB / "owltunes.pretty" / f"{name}.kicad_mod").read_text()
            self.assertEqual(set(re.findall(r'\(pad "([^"]*)"', text)), pads_, name)
            self.assertIn("F.CrtYd", text, name)
            model = re.search(r'\(model "\$\{KIPRJMOD\}/\.\./lib/3dmodels/([^"]+)"', text)
            self.assertIsNotNone(model, name)
            if (LIB / "3dmodels").is_dir():  # models are rebuilt locally, not tracked
                self.assertTrue((LIB / "3dmodels" / model.group(1)).is_file(), name)

    def test_land_patterns_match_the_datasheets(self):
        for name, want in LANDS.items():
            have = pads((LIB / "owltunes.pretty" / f"{name}.kicad_mod").read_text())
            land_matches(self, name, have, want)

    def test_printed_dimensions_measure_right(self):
        """The dimensions as the drawings print them, measured between pad edges and centres."""

        def fp(name):
            return {p["number"] + ("" if p["number"] != "MP" else str(i)): p for i, p in
                    enumerate(pads((LIB / "owltunes.pretty" / f"{name}.kicad_mod").read_text()))}

        def edge(p, side):
            return {"l": p["x"] - p["w"] / 2, "r": p["x"] + p["w"] / 2, "t": p["y"] - p["h"] / 2,
                    "b": p["y"] + p["h"] / 2}[side]

        d = fp("TI_DLA_VSON-10_2x3mm_P0.5mm")
        self.assertAlmostEqual(d["2"]["y"] - d["1"]["y"], 0.5, delta=0.001)  # 8X (0.5)
        self.assertAlmostEqual(d["6"]["y"] - d["10"]["y"], 2.0, delta=0.001)  # (2)
        self.assertAlmostEqual(edge(d["8"], "r") - edge(d["8"], "l"), 1.3, delta=0.001)  # (1.3)
        self.assertAlmostEqual(edge(d["10"], "r") + edge(d["1"], "l"), 0.0, delta=0.001)  # outer ends symmetric
        m = fp("Maxim_TDFN-8-1EP_2x2mm_P0.5mm")
        self.assertAlmostEqual(m["1"]["y"] - m["8"]["y"], 1.98, delta=0.001)  # 1.98
        self.assertAlmostEqual(m["2"]["x"] - m["1"]["x"], 0.50, delta=0.001)  # 0.50
        self.assertAlmostEqual(edge(m["1"], "b") - edge(m["1"], "t"), 0.70, delta=0.001)  # 0.70
        o = fp("TI_DNP_USON-6-1EP_2x2mm_P0.65mm")
        self.assertAlmostEqual(o["1"]["y"] - o["6"]["y"], 1.9, delta=0.001)  # (1.9)
        self.assertAlmostEqual(o["3"]["x"] - o["1"]["x"], 1.3, delta=0.001)  # 2X 1.3
        h = fp("Hirose_FH26W-31S-0.3SHW_1x31-1MP_P0.30mm_Horizontal")
        self.assertAlmostEqual(edge(h["1"], "t") - edge(h["2"], "b"), 2.15, delta=0.001)  # 2.15 +- 0.05
        self.assertAlmostEqual(edge(h["1"], "b") - edge(h["2"], "t"), 3.6, delta=0.001)  # (3.6)
        self.assertAlmostEqual(h["31"]["x"] - h["1"]["x"], 9.0, delta=0.001)  # C
        self.assertAlmostEqual(h["30"]["x"] - h["2"]["x"], 8.4, delta=0.001)  # B
        self.assertAlmostEqual(h["2"]["x"] - h["1"]["x"], 0.3, delta=0.001)  # 0.3 overall pitch
        tabs = sorted((p for k, p in h.items() if k.startswith("MP")), key=lambda p: p["x"])
        self.assertAlmostEqual(edge(tabs[1], "l") - h["31"]["x"], 0.5, delta=0.001)  # 0.5 +- 0.05
        self.assertAlmostEqual(edge(h["31"], "b") - edge(tabs[1], "b"), 0.2, delta=0.001)  # 0.2 +- 0.05
        self.assertAlmostEqual(h["1"]["x"] - edge(tabs[0], "r"), 0.5, delta=0.001)
        f = fp("L_Murata_DFE201612E")
        self.assertAlmostEqual(edge(f["2"], "r") - edge(f["1"], "l"), 2.4, delta=0.001)  # 2.4
        self.assertAlmostEqual(edge(f["2"], "l") - edge(f["1"], "r"), 0.8, delta=0.001)  # 0.8

    def test_pin_one_is_where_the_datasheet_draws_it(self):
        corner = {  # (sign of x, sign of y) of pad 1
            "TI_DLA_VSON-10_2x3mm_P0.5mm": (-1, -1),  # top left, pins down the left side
            "Maxim_TDFN-8-1EP_2x2mm_P0.5mm": (-1, 1),  # bottom left, pins along the bottom
            "TI_DNP_USON-6-1EP_2x2mm_P0.65mm": (-1, 1),
            "Hirose_FH26W-31S-0.3SHW_1x31-1MP_P0.30mm_Horizontal": (-1, 1),  # left end of the FPC-side row
            "L_Murata_DFE201612E": (-1, 0),
        }
        for name, (sx, sy) in corner.items():
            have = pads((LIB / "owltunes.pretty" / f"{name}.kicad_mod").read_text())
            one = next(p for p in have if p["number"] == "1")
            self.assertEqual((round(one["x"], 6) > 0) - (round(one["x"], 6) < 0), sx, name)
            self.assertEqual((round(one["y"], 6) > 0) - (round(one["y"], 6) < 0), sy, name)
            numbered = [p for p in have if p["number"].isdigit()]
            self.assertEqual(min(p["x"] for p in numbered if (p["y"] > 0) == (one["y"] > 0)), one["x"], name)

    def test_pogo_pin_hole_takes_the_post(self):
        have = pads((LIB / "owltunes.pretty" / "PogoPin_Xinyangze_YZ71215080P-02.kicad_mod").read_text())
        holes = [p for p in have if p["kind"] == "thru_hole"]
        self.assertEqual(len(holes), 1)
        self.assertAlmostEqual(holes[0]["drill"], POGO_DRILL, delta=0.001)
        self.assertGreaterEqual(holes[0]["w"] - holes[0]["drill"], 0.3 - 1e-6)  # 0.15 mm annular ring

    def test_paste_apertures_follow_the_stencil_examples(self):
        # TPS63802 SLVSEU9D p. 37: pad 8 printed at 83 % (two 0.55 x 0.25 openings, here one 1.1 x 0.25);
        # OPT3001 SBOS681C p. 43: thermal pad opening 0.62 x 1.25 (here turned, 1.25 x 0.62); Maxim gives
        # no stencil, the exposed pad prints 0.05 mm in from its edge. Every other pad prints in full.
        want = {
            "TI_DLA_VSON-10_2x3mm_P0.5mm": {"8": (1.1, 0.25)},
            "Maxim_TDFN-8-1EP_2x2mm_P0.5mm": {"9": (1.28, 0.70)},
            "TI_DNP_USON-6-1EP_2x2mm_P0.65mm": {"7": (1.25, 0.62)},
        }
        for name in PADS:
            have = paste_apertures((LIB / "owltunes.pretty" / f"{name}.kicad_mod").read_text())
            exp = want.get(name, {})
            self.assertEqual(sorted(have), sorted(exp), name)
            for n, (w, h) in exp.items():
                self.assertAlmostEqual(have[n][0], w, delta=0.002, msg=f"{name} pad {n}")
                self.assertAlmostEqual(have[n][1], h, delta=0.002, msg=f"{name} pad {n}")

    def test_inductor_keeps_tracks_and_vias_from_under_the_coil(self):
        # Murata DFE201612E reference specification p. 7: no through holes or copper under the coil
        # except the electrodes. A rule area on the part's copper side covers the gap between the pads.
        text = (LIB / "owltunes.pretty" / "L_Murata_DFE201612E.kicad_mod").read_text()
        zone = re.search(r"\(zone(.*?)\n\t\)", text, re.S)
        self.assertIsNotNone(zone)
        body = zone.group(1)
        self.assertRegex(body, r'\(layers? "F\.Cu"\)')  # KiCad writes one layer as (layer ...)
        for item in ("tracks", "vias", "copperpour"):
            self.assertRegex(body, rf"\({item} not_allowed\)")
        pts = [(float(x), float(y)) for x, y in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", body)]
        self.assertEqual((min(p[0] for p in pts), max(p[0] for p in pts)), (-0.4, 0.4))
        self.assertEqual((min(p[1] for p in pts), max(p[1] for p in pts)), (-0.8, 0.8))

    @unittest.skipUnless(shutil.which("kicad-cli") and (STOCK / "RF_Module.pretty").is_dir(), "needs KiCad 10")
    def test_build_script_reproduces_the_committed_files(self):
        # Edits made by hand in the footprint editor would be lost on the next build; they belong in
        # the tables of tools/hw/hw_lib_build.py.
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(ROOT / "tools" / "hw" / "hw_lib_build.py"), "--offline", "--lib", tmp,
                            "--stock", str(STOCK)], check=True, capture_output=True)
            built = pathlib.Path(tmp)
            self.assertEqual((built / "owltunes.kicad_sym").read_text(), (LIB / "owltunes.kicad_sym").read_text())
            for path in sorted((built / "owltunes.pretty").glob("*.kicad_mod")):
                self.assertEqual(path.read_text(), (LIB / "owltunes.pretty" / path.name).read_text(), path.name)

    def test_courtyards_clear_every_pad(self):
        for name in PADS:
            text = (LIB / "owltunes.pretty" / f"{name}.kicad_mod").read_text()
            have = pads(text)
            x0, y0, x1, y1 = courtyard(text)
            px0 = min(p["x"] - p["w"] / 2 for p in have)
            px1 = max(p["x"] + p["w"] / 2 for p in have)
            py0 = min(p["y"] - p["h"] / 2 for p in have)
            py1 = max(p["y"] + p["h"] / 2 for p in have)
            for margin in (px0 - x0, x1 - px1, py0 - y0, y1 - py1):
                self.assertGreaterEqual(margin, 0.2 - 1e-6, name)
                self.assertLessEqual(margin, 1.0, name)

    def test_no_drill_below_the_jlc_no_fee_size(self):
        for path in (LIB / "owltunes.pretty").glob("*.kicad_mod"):
            for drill in re.findall(r"\(drill (?:oval )?([0-9.]+)", path.read_text()):
                self.assertGreaterEqual(float(drill), 0.3 - 1e-3, path.name)

    def test_module_copy_keeps_the_stock_pads(self):
        text = (LIB / "owltunes.pretty" / "ESP32-S3-WROOM-1_Drill0.3.kicad_mod").read_text()
        pads_ = re.findall(r'\(pad "([^"]*)"', text)
        self.assertEqual(len(pads_), 62)  # 41 numbered pads, 12 thermal vias on pad 41, 9 paste openings
        self.assertEqual(set(pads_), {str(n) for n in range(1, 42)} | {""})
        self.assertEqual(re.findall(r"\(drill ([0-9.]+)\)", text), ["0.3"] * 12)
        stock = STOCK / "RF_Module.pretty" / "ESP32-S3-WROOM-1.kicad_mod"
        if stock.is_file():  # the only differences from KiCad's footprint are the name and the drills
            mine = pads(text)
            theirs = pads(stock.read_text())
            self.assertEqual([{**p, "drill": None} for p in mine], [{**p, "drill": None} for p in theirs])

    @unittest.skipUnless(STOCK.is_dir(), "KiCad footprint library not installed")
    def test_stock_footprints_match_the_datasheets(self):
        for name, want in STOCK_LANDS.items():  # KiCad rounds the EVQP7A rows to 0.72 (catalogue 0.725)
            land_matches(self, name, pads((STOCK / f"{name}.kicad_mod").read_text()), want, tol=0.01)

    @unittest.skipUnless(STOCK.is_dir(), "KiCad footprint library not installed")
    def test_stock_sot23_6_covers_the_ti_dbv_land(self):
        # TMAG5273 SLYS045C p. 55 (DBV0006A-C02): pads 1.1 x 0.6, 0.95 pitch, rows 2.6 apart. KiCad's
        # IPC land is longer towards the body; it must cover TI's pad to within 0.05 mm at the toe.
        have = pads((STOCK / "Package_TO_SOT_SMD.pretty" / "SOT-23-6.kicad_mod").read_text())
        for p in have:
            n = int(p["number"])
            ti_x = -1.3 if n <= 3 else 1.3
            ti_y = {1: -0.95, 2: 0.0, 3: 0.95, 4: 0.95, 5: 0.0, 6: -0.95}[n]
            self.assertAlmostEqual(p["y"], ti_y, delta=0.005)
            self.assertAlmostEqual(p["h"], 0.6, delta=0.005)
            self.assertLessEqual(abs(p["x"]) - p["w"] / 2, abs(ti_x) - 0.55 + 0.005)
            self.assertGreaterEqual(abs(p["x"]) + p["w"] / 2, abs(ti_x) + 0.55 - 0.05 - 0.005)


if __name__ == "__main__":
    unittest.main()
