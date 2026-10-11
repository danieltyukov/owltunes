# OwlTunes KiCad library

Parts the KiCad 10 stock library lacks: five symbols (`owltunes.kicad_sym`) and seven footprints
(`owltunes.pretty/`). `tools/hw/hw_lib_build.py` writes them all from tables typed from the
datasheets: pin names and electrical types for the symbols, the manufacturers' land patterns for
the footprints. `tools/tests/test_hw_library.py` checks the files against a second set of tables,
written the way each datasheet dimensions its drawing, and checks that the build script still
reproduces the committed files (so an edit made in the footprint editor fails the test; change
the tables instead).

```
python3 tools/hw/hw_lib_build.py              # download from LCSC/EasyEDA, compare, write, copy 3D models
python3 tools/hw/hw_lib_build.py --offline    # write the tracked files only (no network)
python3 -m unittest tools/tests/test_hw_library.py
```

JLC2KiCadLib downloads each part's EasyEDA symbol, footprint and STEP model. The symbols and
footprints are not used directly: the build prints how far EasyEDA differs from the datasheet
(pin names agree for all five symbols; footprints differ by up to 0.075 mm on the TPS63802,
0.275 mm on the MAX17048, 0.05 mm on the OPT3001 and the FH26W fitting tabs, 0.33 mm on the
inductor; EasyEDA's pogo pin hole has no copper ring). The STEP models are copied to `3dmodels/`, placed by the offsets in the build script.

## Parts

Pages are those of the document named, as printed on the page.

| Item | LCSC | Symbol pins from | Footprint from | Checked |
|---|---|---|---|---|
| TPS63802DLAR symbol, `TI_DLA_VSON-10_2x3mm_P0.5mm` | C2845237 | TPS63802 datasheet SLVSEU9D, table 7-1 | TI DLA0010A example board layout | p. 4 (pins); p. 36 land pattern, p. 37 stencil (pad 8 at 83 %), p. 35 outline |
| MAX17048G+T10 symbol, `Maxim_TDFN-8-1EP_2x2mm_P0.5mm` | C2682616 | MAX17048 datasheet 19-6171 rev 7, pin description | Maxim land pattern 90-0065 rev E (package T822, outline 21-0168) | p. 6 (pins, top view); p. 18 package table; 90-0065 p. 1 |
| TMAG5273A2QDBVR symbol (stock `SOT-23-6`) | C3715882 | TMAG5273 datasheet SLYS045C, table 4-1 | KiCad stock, compared with TI DBV0006A-C02 | p. 4 (pins); p. 55 land pattern |
| LIS2DW12TR symbol (stock `LGA-12_2x2mm_P0.5mm`) | C189624 | LIS2DW12 datasheet DS11811 rev 9, table 1 | KiCad stock, compared with the package and ST TN0018 | p. 4 (pins); p. 56 package; TN0018 rev 8 p. 12 |
| OPT3001DNPR symbol, `TI_DNP_USON-6-1EP_2x2mm_P0.65mm` | C90462 | OPT3001 datasheet SBOS681C, pin functions | TI DNP0006A example board layout | p. 3 (pins); p. 42 land pattern, p. 43 stencil (thermal pad 88 %), p. 41 outline |
| `Hirose_FH26W-31S-0.3SHW_1x31-1MP_P0.30mm_Horizontal` | C2973806 | (stock connector symbols) | Hirose drawing EDC3-323714-05, recommended PCB mounting pattern | p. 1 pattern and side view, p. 4 table (31 contacts: B 8.4, C 9.0), p. 6 bottom contact; FH26 series catalogue (Oct 2026) p. 8 |
| `PogoPin_Xinyangze_YZ71215080P-02` | C5157364 | (stock symbol) | Xinyangze drawing YZ71215080P-02 (part only, no land pattern) | p. 3 of the LCSC file |
| `L_Murata_DFE201612E` | C668312 | (stock `Device:L`) | Murata reference specification J(E)TE243A-0006B-01, recommended PCB pattern | p. 5 pattern, p. 1 size, p. 7 no copper under the coil |
| `ESP32-S3-WROOM-1_Drill0.3` | C2913202 | (stock symbol) | KiCad stock footprint, thermal vias opened from 0.2 to 0.3 mm; antenna keep-out and courtyard cut to the owl notch plus 3 mm strips (Espressif's 15 mm keep-out does not fit in the 66 x 84 mm owl; bring-up RSSI and the ring test decide WROOM-1 or WROOM-1U) | via spacing 0.99 mm, ring 0.15 mm |

Stock footprints the boards use, checked against the manufacturers (the test repeats these
checks wherever KiCad is installed):

| Footprint | Compared with | Result |
|---|---|---|
| `Button_Switch_SMD:SW_SPST_EVQP7A` | Panasonic EVQP7 catalogue p. 2, PWB land pattern (5.0 / 2.2 across, 2.5 / 0.4 down) | Match (KiCad rounds the row centres to 0.72, catalogue 0.725); terminal 1 on the top pair, knob towards +Y |
| `Button_Switch_SMD:SW_SPST_TS-1088-xR020` | XUNPU TS-1088 drawing for C720477, PCB welding drawing (5.50 / 3.40, 2.00) | Match |
| `Package_LGA:LGA-12_2x2mm_P0.5mm` | LIS2DW12 DS11811 rev 9 p. 56 (terminals 0.275 x 0.25, 0.1 from the edge) and ST TN0018 rev 8 p. 12 (land = terminal + 0.1 mm) | Match; pin 1 top left, counter-clockwise |
| `Package_TO_SOT_SMD:SOT-23-6` | TMAG5273 SLYS045C p. 55, DBV0006A-C02 (1.1 x 0.6 pads, rows 2.6 apart) | Accepted: KiCad's IPC land (1.325 x 0.6 at 2.275) covers TI's pad except 0.05 mm at the toe; shared with U104 and U202 |
| `Inductor_SMD:L_Murata_DFE201610P` | Murata DFE201612E p. 5 (0.8 x 1.8 pads, 2.4 overall) | Rejected: drawn for the 1.0 mm DFE201610P (0.55 x 1.6 pads, 2.0 overall), up to 0.25 mm off. Use `owltunes:L_Murata_DFE201612E` |

## How the footprints are drawn

- Every pad is the manufacturer's recommended land. Where the datasheet gives a stencil, the paste
  openings follow it: TPS63802 pad 8 (p. 37), OPT3001 thermal pad (p. 43), and every FH26W
  contact and tab (drawing p. 1, recommended stencil pattern: openings 0.23 wide, 0.55 long on
  the even row and 0.65 long on the odd row, flush with the pads' outer ends, 2.4 between them;
  tab openings 0.3 x 0.7 on the tab's outer side). KiCad's paste margins shrink a pad evenly, so
  the FH26W contacts carry no paste of their own and the openings are separate paste-only pads
  (unnumbered, as in KiCad's ESP32 module footprint). Maxim gives no stencil for the TDFN; its
  exposed pad prints 0.05 mm in from the edge (81 %). Other pads print in full.
- Each footprint keeps the orientation of the part's EasyEDA footprint, which is JLC's zero
  rotation, so the placement file needs no rotation offset for these parts (confirm in JLC's
  placement preview when ordering). TPS63802: pin 1 top left, pins 1 to 5 down the left side.
  MAX17048 and OPT3001: pin 1 bottom left, pins 1 to 4 (1 to 3) along the bottom, as in the
  MAX17048 top view. The origin is the package centre (the EasyEDA TPS63802 footprint is 0.075 mm
  off it).
- FH26W: contact 1 at the left of the odd row, which is the FPC side (+Y, marked with an arrow on
  F.Fab); the flip actuator hinges at the back (-Y). Bottom contact: the FPC goes in with its
  conductors facing the board (drawing p. 6). The current FH26 series catalogue orders the series
  as FH26W and draws the same pattern; a drawing of the older FH26-31S-0.3SHW used on the
  Waveshare board (not stocked by JLC) was not available to compare directly.
- Pogo pin: no land pattern is published. The 2.2 mm pad is the 2.0 mm flange plus 0.1 mm; the
  0.60 +-0.03 mm locating post goes into a plated 0.8 mm hole (at least 0.72 mm with JLCPCB's
  -0.08 mm plated-hole tolerance). The paste is a ring from 0.55 mm (0.15 mm clear of the hole)
  to the pad edge, so none of it runs into the hole. The pin stands 7.0 mm above the board free
  and 6.0 mm working. The footprint type is SMD although it has a plated hole, because JLC places
  the part as SMD (LCSC lists it as SMD): it stays in a placement file exported with KiCad's
  SMD-only option, and the Fabrication Toolkit lists it either way. KiCad's footprint_type_mismatch
  check is set to ignore in both projects, so DRC does not judge this choice.
- Murata DFE201612E: a rule area on the part's copper side keeps tracks, vias and copper pour out
  of the gap between the electrodes (p. 7: the core's insulation resistance is low).
- Courtyards are the pads, the body and the silkscreen plus 0.25 mm. Silkscreen lines are 0.15 mm
  and stay 0.2 mm clear of copper; a dot marks pin 1.
- No drill is below 0.3 mm. The module copy keeps KiCad's 0.6 mm via pads, so the ring is 0.15 mm.

## 3D models

`3dmodels/` holds the EasyEDA STEP models. EasyEDA's licence for them is unclear, so they are not
tracked: `python3 tools/hw/hw_lib_build.py` recreates them locally (network needed). Footprints
point at `${KIPRJMOD}/../lib/3dmodels/<footprint>.step`. Placement corrections in the build script:
the TPS63802 model's top face is at z = 0 (lifted 0.95 mm); the inductor model is a 1.0 mm generic
body, scaled to Murata's 1.2 mm.
