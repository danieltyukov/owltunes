# Ordering (rev A)

Everything for the first build is ordered in one session: both boards and the prints from JLC,
then the parts that are not on the boards. Upload to JLC before Wednesday 28 October 2026. A
private order package (shops, prices and the order-day checklist) is kept outside the repository.

## Before uploading

Decide on the adapter fit check first (rev-a.md, Open items). Then run these in the
repository on the order day and stop at the first failure:

```
python3 tools/hw/hw_stock.py owl-mainboard --boards 5
python3 tools/hw/hw_stock.py perch-dock --boards 5
python3 tools/hw/hw_fab.py owl-mainboard
python3 tools/hw/hw_fab.py perch-dock
tools/hw/check_all.sh
```

Every stock line must read `OK` (a `LOW` part switches to its `alt` in `design.toml`, same
footprint, and the steps run again). `hw_fab.py` must print `0 fabrication error(s)` with
`placements top 18, bottom 78` for the main board and `placements top 15, bottom 0` for the perch
board. The review behind these files is [rev-a-review.md](rev-a-review.md).

## Main board (JLCPCB)

| Setting | Value |
|---|---|
| Gerbers | `hardware/owl-mainboard/production/owl-mainboard.zip` from `python3 tools/hw/hw_fab.py owl-mainboard` |
| Base material, layers, thickness | FR-4, 4 layers, 1.0 mm |
| Stack-up | JLC04101H-7628 (7628 prepreg 0.2104 mm, core 0.4788 mm), as in the board file; no impedance control (USB is full speed) |
| Surface, mask, silkscreen | ENIG, green, white |
| Via covering | Tented |
| Quantity | 5 (JLC's minimum for bare boards) |
| Edge rails and fiducials | Added by JLCPCB (the board has no fiducials). Ask for tab routing, not V-cut, in the order remark: the outer pours and the stitching vias sit 0.3 to 0.5 mm from the edge and the outline is rounded. Ask in the same remark for no tabs at J201 (the USB-C overhangs the bottom edge by 1 mm), SW203 (0.15 mm from the bottom edge) and SW201, SW202 (their knobs face the top edge). File each tab nub flush before the board goes into the enclosure |
| Remove order number | Specify a location (text JLCJLCJLCJLC on B.Silkscreen under the battery) |
| PCB Assembly | Standard, both sides, quantity 3 |
| Confirm parts placement | Yes |
| BOM, CPL | `production/bom.csv` (47 rows, 45 LCSC numbers, 96 designators), `production/positions.csv` (96 parts: 18 top, 78 bottom) |
| Rotation offsets set | D101 180, D102 180, J101 180, U202 90, U303 270 (`FT Rotation Offset`, from `rotation_offset` in design.toml): offset set from the EasyEDA pad match; confirm in the preview. Method: each part's EasyEDA footprint, which JLC places from, compared pad by pad with the KiCad footprint, less the Fabrication Toolkit's own table rotation ([rev-a-review.md](rev-a-review.md), Findings fixed). The bottom-side rotations assume JLC turns bottom parts the way the toolkit does. That is one decision for the whole board: if it is the other way, every bottom part at 90 or 270 in the CPL shows 180 degrees off at once, and the polarised ones are U104, U202, U301, U303, J101, J202 and J302 (the rest at 90 or 270 are passives, L101 and Y201, which do not care). Then add 180 to the rotation_offset of all seven together (U104 180, U202 270, U301 180, U303 90, J101 0, J202 180, J302 180); parts at 0 or 180 are unaffected. Check every other polarised part in the preview too, before paying. To change an offset, edit its value in design.toml and on the symbol (0, or "0,0" for a position, drops it, so all three copies stay in step), run `hw_sync.py`, `hw_kicad.py` and `hw_fab.py`, and list it here |
| Position offsets set | U201 0,-3.627 and J201 0,1.571 (`FT Position Offset`, from `position_offset` in design.toml): offset set from the EasyEDA pad match; confirm in the preview. The toolkit places the CPL point on the KiCad anchor (the body centre for these two), JLC on the EasyEDA footprint's origin (near the pad pattern's centre). The preview checks the positions of U201 and J201 as well as every rotation |
| Touch level shift parts | U305 TI LSF0204PWR (C202288, TSSOP-14) and U306 Torex XC6206P182MR (C21659, SOT-23) are JLC Extended parts with no Basic or Preferred equivalent (alternates: C2677502 LSF0204QPWRQ1 with the same pins, C347373 UMW XC6206P182MR). Do not substitute the LSF0204D, whose EN is active low. Check the pin 1 mark of U305 in the placement preview. R315 (0R) is not assembled |

## Perch board with the dock-pad section (JLCPCB)

| Setting | Value |
|---|---|
| Gerbers | `hardware/perch-dock/production/perch-dock.zip` from `python3 tools/hw/hw_fab.py perch-dock` |
| Layers, thickness | 2, 1.6 mm |
| Surface, mask | ENIG (gold pads for the pogo contacts), green |
| Quantity | 5 |
| Board shape | One design: the dock-pad section hangs on a mouse-bite neck. If JLC asks, it is one design with a breakaway section, not a panel of several designs |
| Edge rails and fiducials | If JLC asks, the same answer as the main board: added by JLCPCB (the board has no fiducials), tab routing, not V-cut. Ask in the order remark for no tabs at J1 (its shell overhangs the right edge by 0.5 mm) or in the dock-pad section's key notch. File each tab nub flush, on the dock-pad section too: it sits in a recess with 0.2 mm clearance |
| PCB Assembly | Economic, top side, quantity 3 |
| BOM, CPL | `production/bom.csv`, `production/positions.csv` (15 parts, all top) |
| Remove order number | No: JLC prints its number where it likes. The perch board is hidden in the perch body and the dock-pad section behind the owl's back cover, which shows only the gold pads through their windows |
| Rotation offsets set | None (checked in the placement preview: J1, J2, D1, D2, LED1, P1 to P3) |
| Position offsets set | J1 `FT Position Offset` 0,1.571 (from `position_offset` in design.toml): offset set from the EasyEDA pad match; confirm in the preview that J1 sits on its pads |

## Prints (JLC3DP, MJF PA12, standard finish, quantity 1 each)

Export the files from the current enclosure code on the order day (`uv run --project enclosure
python enclosure/owl_v1.py`, and the same for `perch_v1.py` and `ring_test.py`), so the uploads
carry the latest changes.

The ring test ([ring-test.md](ring-test.md)) has not run yet, and the order is a single session,
so it buys both ring variants and both magnet carriers. The test then picks ring A (6710 bearing)
or ring B (printed bushing) and 24 or 32 magnets with the parts in hand; the unused variant is a
spare. The rings and the bushing sleeve are the same geometry in `v1/` and `ring-test/`, so they
are printed once and serve both.

| Folder | Files | Colour |
|---|---|---|
| `build/enclosure/v1/` | body (with the cable relief behind J303), back_cover (with the Tyukov Inc mark and the slot in the LRA cup for the motor's lead tab), bezel, glass_retainer, ring_a_bearing, ring_b_bushing, bushing_sleeve, beak_key, ear_key_left, ear_key_right, magnet_carrier_24, magnet_carrier_32 | black dyed |
| `build/enclosure/perch-v1/` | perch_body (with the Tyukov Inc mark on the underside) | black dyed |
| `build/enclosure/ring-test/` | face_bezel, sensor_jig, coupon_shaft, coupon_bore, magnet_carrier_24, magnet_carrier_32 (these two with polarity bumps, for the test), jig_spacer_1mm, jig_spacer_2mm, jig_spacer_3mm | natural grey |

## Parts that are not on the boards

Quantities are for the first build: 3 assembled main boards, 3 assembled perch boards, one owl
enclosure and one perch.

| Part | Source | Quantity |
|---|---|---|
| Battery: 2-wire 1S LiPo, 803030 class (8 x 30 x 30 mm: efaso 803030 740 mAh, or EEMB 803030 700 mAh if its plug is confirmed as PH 2.0), protection circuit, JST PH 2.0 2-pin plug; it sits in the 803040 cavity against a foam end stop ([assembly.md](assembly.md) step 8). J101 pin 1 is VBAT and pin 2 is GND; check every pack's polarity before plugging it in (J101 has no reverse-polarity protection, [assembly.md](assembly.md) step 6). No NTC wire: the charger reads RT101 on the board | any | 2 (one spare) |
| Thermal gap pad for RT101: soft, electrically insulating silicone, 1.5 mm thick, 1 to 3 W/mK, cut to about 5 x 5 mm ([rev-a.md](rev-a.md), Off-board parts) | any | 1 small sheet |
| LRA Leader LD0832AA-0099F (C2682305), alternate LD0832AA-0126F (C2942349) | LCSC | 4 |
| JST SH 1.0 mm 2-pin pigtail, pre-crimped, single ended, about 10 cm, 28 or 30 AWG, for the LRA (soldered to the motor's leads under heat shrink) | any | 1 pack of 10 |
| 1 mm double-sided foam tape (battery end stop) and 1.5 mm heat-shrink tubing (LRA splices) | any | 1 roll each |
| JST SH 4-pin cable, 50 mm, pin 1 to pin 1 (Qwiic or STEMMA QT, for example Adafruit 4399), J303 to the dock-pad board | any | 3 |
| ESP32-S3-WROOM-1U-N16R8 (C3013946), loose: the fallback if the ring test loses more than 6 dB of RSSI, swapped by hand onto one board | LCSC | 2 |
| 2.4 GHz antenna with a U.FL (IPEX MHF1) plug for the WROOM-1U, for example Molex 146153-0050 (C916292) | LCSC | 2 |
| VIEWE 1.75 inch AMOLED ALL-UEOL018WV-RA31-A001A (the shop lists ALL-UEOL018VG-RA31-A001A) in the 48.16 mm cover glass version (order code from VIEWE; the one the shop lists is not confirmed to be it), plus the standard adapter FPC FPC3-HD143Y002M (31 contacts, 0.3 mm pitch, USD 0.80 each), ordered separately | VIEWE | 2 panels, 2 adapters |
| Bearing 6710ZZ, 50 x 62 x 6 mm (ring A and the ring test) | any | 2 |
| N52 disc magnets D3 x 2 mm, axially magnetised (ring carriers) | any | 150 |
| N52 disc magnets D6 x 2 mm, axially magnetised (dock: 2 in the owl, 2 in the perch) | any | 8 |
| O-ring NBR 59 x 1.5 mm (ring B drag) | any | 1 pack |
| Damping grease for camera focus rings (ring B feel) | any | 1 small tube |
| ISO 7380 M2 button-head screws, black: M2 x 6 (front, 4 per owl) and M2 x 14 (back, 4 per owl); M2 x 8 or M2 x 10 with nuts for the ring-test jig | any | 1 pack each |
| M2 heat-set inserts, 3.0 mm long, 3.6 mm outside (8 per owl) | any | 1 pack |
| M2 x 5 self-tapping pan-head screws (perch board) | any | 2 per perch |
| Steel weight for the perch, 70 x 40 x 9 mm (pocket 72 x 42 x 9.2 mm; 40 x 8 mm flat bar cut to 70 mm works) | any | 1 |
| Silicone feet for the perch, about 8 to 10 mm across (for example 3M Bumpon SJ5302) | any | 1 sheet (4 per perch) |
| SparkFun TMAG5273 Qwiic board (SEN-23880) and a Qwiic breadboard cable, for the ring test | any | 1 each |
| Cyanoacrylate glue (magnets, ring-test parts; keep it away from the cover glass) | any | 1 |

The ring test ([ring-test.md](ring-test.md)) uses the steel 6710ZZ for ring A and the printed
bushing as the metal-free ring B; no plastic 6710 is bought (ruling R14). If the steel bearing
costs more RSSI than ring-test.md allows, ring B is chosen. The RSSI runs (M4) use the owner's
Arduino Nano ESP32 (NORA-W106, PCB antenna), measured relative: with and without the ring stack.
