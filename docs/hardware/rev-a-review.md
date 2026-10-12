# Rev A design review

Two sections: the perch dock board (11 October 2026) and the main board (12 October 2026, after
routing, on the fabrication files that are uploaded).

## Perch dock board (perch-dock, 2 layers, 34.0 x 29.0 mm with the dock-pad section)

Verdict: ready to order, subject to the placement preview rotation check at order time
(listed in the private order notes). Blockers: none.

### Blockers

| Finding | Status |
|---|---|
| none | |

### Checks run

| Check | Result |
|---|---|
| ERC (`hw_kicad.py perch-dock`) | 0 violations |
| DRC with schematic parity | 0 violations, 0 unconnected, 0 parity |
| `hw_fab.py perch-dock` | 0 fabrication errors; 15 placements, all top; BOM 14 rows, 15 designators; CPL equals `design.toml` |
| Gerber analysis (`analyze_gerbers.py`) | complete: F/B Cu, F/B mask, F/B silkscreen, F/B paste, Edge.Cuts, PTH and NPTH drills; board 34.0 x 29.0 mm; layers aligned; 0 findings |
| kicad-happy schematic analysis | 13 findings, none blocking (see below) |
| kicad-happy PCB analysis (`--full`) | 28 findings, none blocking (see below) |
| kicad-happy cross analysis | 0 findings |
| kicad-happy EMC analysis | 8 findings, none blocking (see below) |
| kicad-happy thermal analysis | 0 findings |

### Findings accepted, with the reason

| Rule | Finding | Reason |
|---|---|---|
| KO-001 (error) | MB1 and MB2 inside the neck keep-out | False positive. The keep-out forbids tracks, vias and copper pours; footprints and pads are allowed. The mouse-bite holes are the footprints meant to sit in the neck. |
| FD-001 (error) | No fiducials on F.Cu | Accepted. 15 parts, none finer than 0402 and no fine-pitch IC, so placement accuracy does not depend on fiducials. |
| GP-001 (error and warning) | Reference plane gaps on PAD_DET and DOCK_ID | Accepted. Both are DC detect levels, no switching edges; the board carries 5 V power and a few mA. |
| GP-005, BE-001, BE-002, RP-001, SU-001, EE-001 | Ground domain, edge, stitching and resonance notes | Accepted. Two-layer power-only board, no signal above DC; the second ground domain is the isolated pad section ground (PAD_GND) which reaches the board only through the owl's own cabling. |
| UC-001 | No capacitor on VBUS_IN at J1 | Accepted. C1 (10 uF) and C2 (100 nF) sit on VBUS_OUT behind the 1.1 A fuse F1; the board has no USB data and no downstream regulator. |
| UC-002 | No TVS on VBUS_IN at J1 | False positive. D1 (SMF5.0A, unidirectional TVS) is on VBUS_IN to GND; the detector does not know the SMF series. |
| RS-001 | VBUS_OUT has no declared source | False positive. VBUS_OUT is fed from VBUS_IN through the fuse F1 (a passive); ERC passes. |
| PM-002 | F1 0.87 mm from the board edge | Accepted. The edge is a plain outline edge with no depanel cut near the fuse; DRC edge clearance passes. |
| TE-001 | No test points | Accepted. Every net is on a pad, connector pin or pogo contact. |
| DS-002 | No datasheets directory | Review gap, see below. |
| TB-001 | Tombstoning risk medium on R1, R2, R3, C2 | Accepted. Symmetric pads, standard 0402 land pattern; JLCPCB reflow. |
| LA-AUD | LED1 current | Accepted. About 0.7 mA through R4 (4.7 k from about 5 V), a dim indicator, chosen to keep the dock idle draw low. |

### Analyses not run, and why

| Analysis | Reason |
|---|---|
| Datasheet cross-verification (`datasheets/`) | Not synced. The perch board has no IC; the passive values and the USB-C CC resistors (5.1 k pull-downs on CC1 and CC2) were checked against the USB Type-C specification by hand. |
| SPICE | ngspice is installed, but the board is a fuse, a TVS, an ESD diode and an LED; there is no analog behavior to simulate beyond the LED current above. |
| Lifecycle audit | Needs network access; stock is re-checked with `hw_stock.py` on the day of the order. |
| Prior review delta | This is the first review. |

### Fabrication output notes

- The Fabrication Toolkit names the archive after the title block; `hw_fab.py` renames it to
  `perch-dock.zip` and restores `perch-dock.kicad_pro`, which pcbnew reorders when it saves the
  board.
- Parts with `assembled = false` (H1, H2, PAD1 to PAD3, MB1, MB2) are excluded from the BOM and the
  position file on the board and on the symbols, so schematic parity stays at 0.
- No rotation table entry of the toolkit matches a perch footprint, so the CPL rotation is the
  KiCad rotation. Polarised parts to check in the placement preview: J1, J2, D1, D2, LED1, P1 to P3.
- J1 carries `FT Position Offset` 0,1.571 (12 October 2026, main board section, Findings fixed):
  its CPL point is the EasyEDA footprint's origin, 1.571 mm toward the board centre from the KiCad
  anchor. The preview checks its position as well as its rotation.

## Main board (owl-mainboard, 4 layers, 1.0 mm, 61.8 x 79.8 mm)

Verdict: ready to order, subject to the placement preview rotation check at order time (listed in
the private order notes; five rotation offsets are already set from the footprint comparison
below). Blockers: none.

Reviewed on the fabrication files of 12 October 2026 (`python3 tools/hw/hw_fab.py owl-mainboard`
on commit 3c914ce, board unchanged by the run; regenerated after the rotation offsets, with
Gerbers identical apart from their dates). Analyzers: kicad-happy 2.2.1 (schematic, PCB with
`--full`, cross analysis, EMC, thermal, Gerber, SPICE subcircuits with ngspice, lifecycle);
datasheets read for every IC (table below).

### Blockers

| Finding | Status |
|---|---|
| none | |

### Checks run

| Check | Result |
|---|---|
| ERC (`hw_kicad.py`) | 0 violations |
| DRC with schematic parity (`hw_kicad.py`) | 0 violations, 0 unconnected, 0 parity; 3 silk_edge_clearance markers excluded with comments (J201's receptacle front and U201's pin 1 triangle overhang the edge) |
| Zone fills | The saved fills of all five pours equal a fresh ZONE_FILLER fill (difference 0.0000 mm2), so the Gerbers carry current copper |
| `hw_fab.py owl-mainboard` | 0 fabrication errors; 87 placements, 6 top (SW203, J301, C301, C302, U304, C309) and 81 bottom, as design.toml gives (107 parts, 20 not assembled: TP101 to TP107, TP201 to TP205, H1 to H8); BOM 43 rows, 87 designators, LCSC numbers equal to design.toml; every unassembled part excluded on its symbol and its footprint |
| Gerber analysis (`analyze_gerbers.py`) | complete: F, In1, In2 and B copper, F/B mask, F/B paste, F/B silkscreen, Edge.Cuts, PTH and NPTH drills; board 61.8 x 79.8 mm; layers aligned; 250 vias (0.3 mm), 16 plated component holes (0.3 mm thermal vias: 4 in U101, 12 in U201), 4 plated slots 0.6 mm wide for J201's shell (routed, which the analyzer counts as 0 holes), 2 NPTH 0.65 mm (J201 pegs), 8 NPTH 2.2 mm (H1 to H8); 0 errors (no GR-001 to GR-005 error), 1 warning (GR-004, below) |
| kicad-happy schematic analysis | 53 findings: 0 errors, 9 warnings, all triaged below |
| kicad-happy PCB analysis (`--full`) | 108 findings: 7 errors, 31 warnings, all triaged below; routing complete, 0 unrouted nets |
| kicad-happy cross analysis | 3 findings (plane-split artifacts, below) |
| kicad-happy EMC analysis | 45 findings: 5 errors, 32 warnings, all triaged below |
| kicad-happy thermal analysis | 100/100; U103 (TPS63802) Tj about 55 C at 0.2 W. U101 is not modelled by the tool; by hand, (4.65 V - 3.0 V) x 0.478 A = 0.79 W worst case at the start of fast charge, 44.5 C/W (SLUS810N p. 11) gives Tj about 60 C at 25 C ambient, under the 125 C thermal regulation |
| SPICE (`simulate_subcircuits.py`, ngspice) | 16 subcircuits: 15 pass (TPS63802 feedback 0.500 V, the EN, button and DOCK_DET filters, decoupling impedance on VIN_CHG, VSYS, VBAT and +3V3, inrush), 1 warning (crystal, below) |
| Lifecycle | LCSC returns no lifecycle status (all unknown by construction); the TI parts are Active in their datasheets' package addenda (BQ24073RGTR, TPS63802DLAR, TPS22917DBVR, DRV2605LDGSR, TMAG5273A2QDBVR, OPT3001DNPR); stock below |
| Stock (`hw_stock.py owl-mainboard --boards 5`, 12 October 2026) | 43 unique parts, all OK, 0 low or missing |
| Prior review delta | Against the part C analyzer run on the same day (before the polish round): identical findings apart from the GND stitching count (120 to 130 vias, the ten enclosed-pour vias); no finding fixed, none new |

### Datasheet cross-verification

Each IC's pads on the board (pad to net, read with pcbnew) were compared with the pin table of the
manufacturer's datasheet, and the parts each datasheet requires were checked against the
schematic. Pages are the printed page numbers.

| IC | Document | Pages | Checked | Result |
|---|---|---|---|---|
| U101 BQ24073RGTR | TI SLUS810N (October 2021) | p. 7 figure 7-1; pp. 8 and 9 table 7-1 and table 7-2; p. 11 thermal; p. 13 KISET | All 16 pins and the thermal pad; CE (4) to GND; EN2 (5) high through R103, EN1 (6) on CHG_SUSPEND with R104 pull-down: ILIM mode, standby when high; ILIM 3.6k (1.1k to 8k); ISET 2k (590 to 8.9k, 445 mA); TS to RT101 10k NTC; TD (15) to VSS, termination on; TMR (14) open, default timers; IN 4.7 uF (1 to 10 uF); OUT 22 uF and BAT 10 uF (4.7 to 47 uF); PGOOD and CHG with 100k pull-ups (1k to 100k) | Match |
| U103 TPS63802DLAR | TI SLVSEU9D (January 2021) | p. 4 figure 7-1 and table 7-1; p. 6 VFB 500 mV; p. 19 capacitors | EN (1) tied to VIN (always on), MODE (2) low (power save), AGND and GND to GND, FB divider 560k / 100k = 3.30 V, PG open drain to ESP_EN through R212, L1 and L2 to L101 0.47 uH, VIN 10 uF, VOUT 2 x 22 uF (one 22 uF recommended) | Match |
| U104 TPS22917DBVR | TI SLVSDW8B (December 2021) | p. 4 figure 6-1 and table 6-1; p. 15 CT | VIN +3V3, ON = DISP_EN with 100k pull-down, CT 1 nF to VIN (the datasheet ties the CT capacitor to VIN), QOD tied to VOUT (internal discharge), VOUT DISP_3V3 | Match |
| U201 ESP32-S3-WROOM-1-N16R8 | Espressif ESP32-S3-WROOM-1 & WROOM-1U datasheet v1.8 | pp. 11 and 12 table 3-1; p. 13 table 4-1 (strapping) | All 41 pads; IO35 to IO37 left open (octal PSRAM, note b); USB D- on IO19, D+ on IO20; 32 kHz crystal on IO15 and IO16; IO0 (BOOT) 10k pull-up, IO45 (CHG_SUSPEND) and IO46 (DISP_EN) 100k pull-downs, so both read 0 at reset; IO3 strap ignored with the eFuse unburnt; every wake source on an RTC GPIO (IO1 to IO7); EN 47k / 220 nF | Match |
| U301 DRV2605LDGSR | TI SLOS854D (March 2018) | p. 5 DGS pin functions | REG with 1 uF, SCL, SDA, IN/TRIG to GND, EN high, VDD/NC and VDD on +3V3 with 1 uF, OUT+ and OUT- to J302 | Match |
| U302 TMAG5273A2QDBVR | TI SLYS045C (revised April 2026) | p. 4 figure 4-1 and table 4-1 | SCL, GND, GND (TEST) to ground, VCC +3V3, INT with 47k pull-up, SDA | Match |
| U102 MAX17048G+T10 | Maxim 19-6171 rev 7 | p. 6 pin description | CTG to GND, CELL and VDD to VBAT (Kelvin tap at J101), GND, ALRT to GAUGE_ALRT (test pad), QSTRT to GND, SCL, SDA, exposed pad to GND; VDD has 1 uF where 0.1 uF is asked (accepted below) | Match |
| U303 LIS2DW12TR | ST DocID029682 rev 4 (LCSC copy; Task 3 used DS11811 rev 9) | p. 9 table 2; p. 25 application hints | SCL, CS high (I2C), SA0 high through 10k, SDA, NC open, GND, RES to GND, VDD and VDD_IO on +3V3, INT2 open, INT1 to IMU_INT1 | Match |
| U304 OPT3001DNPR | TI SBOS681C (November 2017) | p. 3 pin functions | VDD +3V3, ADDR to GND (0x44), GND, SCL, INT open (open drain, unused), SDA, thermal pad to GND | Match |
| U202 USBLC6-2SC6 | ST Doc ID 11265 rev 5 | p. 1 figure 1 | I/O1 (1, 6) on USB_DP_CONN, I/O2 (3, 4) on USB_DM_CONN, GND (2); VBUS (5) open by design (rev-a.md, Protection and known limits) | Match |
| J301 FH26W-31S-0.3SHW(60) pin 1 | Hirose EDC3-323714-05 | p. 1 recommended PCB mounting pattern | Contact 1 at the end of the row that carries the two fitting tabs (the odd row, contacts 1 to 31), contact 2 at the same end of the other row; on the board contact 1 sits at owl (4.50, 13.44) beside the F.Silkscreen "1", contact 31 beside "31"; pad lengths 0.8 (odd) and 0.65 (even) | Match |

### Findings fixed

Rotation offsets. Each assembled part's EasyEDA footprint (the footprint JLC's placement uses as
zero) was compared pad by pad with the KiCad footprint on the board. The Fabrication Toolkit writes
bottom rotations as 180 minus the KiCad rotation, which is the rotation seen from below with the
board turned over left to right (true for all 81 bottom parts), plus its own table offsets; the
offset a part needs is the EasyEDA-to-KiCad angle less the table's angle. Five parts got an
`FT Rotation Offset` (design.toml `rotation_offset`, the symbol field, copied to the footprint by
`hw_sync.py` and checked by `hw_bom.py` and a test):

| Ref | Offset | Reason |
|---|---|---|
| D101, D102 (PMEG2020EH, C456104) | 180 | EasyEDA's footprint has pad 1, the cathode, on the right at zero; KiCad's D_SOD-123F has it on the left. CPL 180 becomes 0 |
| J101 (S2B-PH-SM4-TB, C295747) | 180 | The EasyEDA footprint matches KiCad's at zero, but the toolkit's `^JST_PH_S` rule adds 180; the offset cancels it. CPL 270 becomes 90 |
| U202 (USBLC6-2SC6, C7519) | 90 | EasyEDA's SOT-23-6 "BL" footprint (rows horizontal, pin 1 bottom left) is 270 from KiCad's; the toolkit's SOT-23 rule gives 180. CPL 180 becomes 270 |
| U303 (LIS2DW12TR, C189624) | 270 | EasyEDA's LGA-12 "BL" footprint runs pins 1 to 4 along the bottom, KiCad's down the left (ruling R30). CPL 180 becomes 90 |

The rest match: U102, U103, U304 and J301 were drawn in EasyEDA's orientation, U104 and U302 use
the SOT-23-6 "BR" footprint the toolkit's 180 fits, U301's TSSOP fits the toolkit's 270, and Y201
differs only in pad numbering (no polarity). The preview still has the last word.

Position offsets (fix round 1). The toolkit puts each SMD part's CPL point on the KiCad
footprint's anchor, while JLC places its EasyEDA footprint by that footprint's origin. Fitting
every EasyEDA footprint onto the board pads by pad number puts the two within 0.075 mm for all
parts but three, where KiCad's anchor is the body centre and EasyEDA's origin is near the pad
pattern's centre. Those get an `FT Position Offset` (design.toml `position_offset`, symbol, and
footprint through `hw_sync.py`, pinned by the same checks), worked through the toolkit's formula
for their side and rotation:

| Ref | Offset | CPL before, after |
|---|---|---|
| U201 (ESP32-S3-WROOM-1, C2913202) | 0,-3.627 | (0, 30.35) to (0, 26.723), 3.627 mm toward the board centre |
| J201 (TYPE-C-31-M-12, C165948) | 0,1.571 | (-12, -33.8) to (-12, -32.229), 1.571 mm toward the board centre |
| Perch J1 (TYPE-C-31-M-12, C165948) | 0,1.571 | (13.8, -1.5) to (12.229, -1.5), 1.571 mm toward the board centre |

Nothing else on the board changed in this review. Fixed before it, in task 10 part C and its polish
round, from the same analyzers and the part C review: GND return vias within 1 mm of every USB via
(RP-001 on the USB nets), stale zone fills after the late hand links, partial copies of hand copper
left by the Specctra import, enclosed outer-pour regions joined with ten GND vias, the board name
moved out from under the H2 cover boss, and labels for the power test pads.

### Findings accepted, with the reason

| Rule | Finding | Reason |
|---|---|---|
| FD-001 (error) | No fiducials on F.Cu or B.Cu | Accepted: there is no room on a board this full. The order selects edge rails with fiducials added by JLCPCB (see Accepted risks). |
| KO-001 (error, 4) | RT101 and its via inside the bat_ntc no-pour areas; J301 inside its keep-out | False positive: those rule areas keep pours and other routes out; RT101, its via and J301's own pads are what they protect. DRC enforces them. |
| PM-002 (error) | SW203 0.15 mm from the edge | By design: the beak switch is pressed through the front shell at the edge (enclosure contract). Its pads keep the 0.3 mm copper to edge rule. |
| PM-002 (info and warning) | J201 overhangs the edge by 1.05 mm; TP101, TP102, TP106 0.6 mm, TP107 0.9 mm, U302 0.85 mm from the edge | By design: the receptacle front overhangs so the plug seats; the rest keep 0.3 mm copper to edge and the board is not V-cut (rails are tab-routed). |
| TV-001 (warning) | U101 4 thermal vias, the tool wants 5 | Accepted: TI's RGT land pattern makes thermal vias optional; four 0.3 mm vias fit the 1.6 mm pad with the paste windows clear of them, the pad joins the planes solid, and the BQ24073 has thermal regulation (Tj about 60 C worst case, above). |
| DFM-001, DFM-002 (warning) | 0.1 mm tracks; 0.1 mm via ring (0.5 / 0.3 mm vias) | Within JLC's 4-layer capability the board's rules use (0.09 mm track and gap; 0.3 / 0.5 mm vias carry no extra fee). |
| CC-002 (warning, 20) | Signal nets with 0.1 to 0.15 mm tracks | Signal currents only; the power nets are 0.5 mm (0.25 mm necks at fine-pitch pins). |
| TE-001 (warning) | Test points on 9 of 76 nets | The bring-up set (rails, reset, boot, UART) is chosen on purpose; I2C and the display are checked from firmware. |
| OR-001, TB-001, CP-002, PM-001 (info) | Mixed passive orientations; 0402 tombstoning risk medium; no copper under the holes; TP202 and TP203 courtyards touching the module's antenna courtyard (0.0 mm2) | Layout follows the parts it serves; standard 0402 lands with JLC reflow; the holes keep a no-copper ring; the test pads sit outside the antenna keep-out, which DRC checks. |
| PU-001 (warning, 4) | U101 TMR, U103 PG, U104 QOD, U303 INT2 have no pull-up | False positive: TMR is left open for the default timers (SLUS810N p. 9); PG is pulled up through R212 (4.7k) and R205 (47k); QOD is tied to VOUT for the internal discharge (SLVSDW8B p. 4); INT2 is a push-pull output left unused. |
| RS-001 (warning, 2) | VBUS_USB and VBUS_DOCK have no declared source | False positive: both are inputs from outside the board (USB-C and the dock cable). |
| UC-001 (warning) | No capacitor on VBUS_USB at J201 | By design: the USB input capacitance sits behind D101 (C101 4.7 uF, under the USB limit of 10 uF); keeping VBUS_USB small limits the attach inrush. |
| UC-002 (warning) | No TVS on VBUS_USB at J201 | False positive: D201 (SMF5.0A, unidirectional TVS) is on VBUS_USB to GND; the tool does not know the SMF series. |
| PS-002 (cross, warning and info) | VSYS, VBAT and +3V3 "plane splits" | False positive: there are no VSYS or VBAT planes and the +3V3 pour is one region; KiCad reports 0 unconnected. The tool's graph splits where a track ends inside a pad off its centre. |
| SU-001 (EMC error, 3) | Adjacent signal layers | False positive: In1 and In2 carry no tracks (GND planes, with the +3V3 pour under the module); KiCad types them signal so the pours can be drawn by script. |
| DC-002 (EMC error) | No decoupling at U202 | By design: U202's VBUS pin is unconnected, so it has no supply to decouple. |
| SW-001, EE-001, EE-002 (EMC) | TPS63802 harmonics in the 30 to 960 MHz bands; board cavity resonances | Estimates for a switching regulator, not layout defects: the hot loops close through In2 GND 0.21 mm under the parts, the input and output caps sit at the pins. No EMC test is planned for rev A. |
| GP-001, RP-001 (EMC warning, 22 nets) | Reference plane gaps and missing return vias at layer changes on slow nets | Accepted: I2C, buttons, interrupts, enables, charger status and LCD reset; In1 GND is under every F.Cu run. BAT_NTC crosses RT101's no-pour area on purpose. See also Accepted risks (the In2 +3V3 boundary). |
| CK-001, CK-003, DP-004 (EMC warning) | LCD_CLK, the 32 kHz crystal, the USB pair and the LRA outputs on outer layers; LCD_CLK near J301 | Microstrip over solid GND is the stack-up's intent; LCD_CLK ends at J301, the connector it is meant to reach; the crystal runs are 5.4 mm over In2 GND. |
| DP-001 (EMC warning) | USB pair skew | About 5.4 mm (30 ps) from J201 to U201 through U202 and R203 / R204; the ESP32-S3 is a full-speed device (12 Mbit/s), so it does not matter. |
| IO-001 (EMC info) | No filtering at J301 | Internal display FPC. |
| GR-004 (Gerber warning) | F.Paste 48 flashes against 319 F.Cu flashes | Expected: the front carries 6 assembled parts (48 paste openings, J301's 33 among them) and the F.Cu count includes 250 via flashes and the back parts' through features. |
| SP-WARN (SPICE) | Crystal Y201 did not resonate in the generic model | Simulator model limit for a 32.768 kHz tuning fork; the load works out at 12 pF (2 x 18 pF in series plus about 3 pF stray) against the crystal's 12.5 pF; bring-up compares the drift (bringup.md step 12). |
| Datasheet (U102) | MAX17048 VDD has 1 uF, the pin table asks for 0.1 uF | Accepted: a larger bypass on a voltage-sense pin is harmless at the gauge's sampling rate. |
| Datasheet (U303) | ST suggests 100 nF and 10 uF at the LIS2DW12 supply | The part has 100 nF and 1 uF at its pins; +3V3 carries 3 x 22 uF a few centimetres away. |

### Accepted risks for this order

| Risk | Why it is accepted | What bring-up does |
|---|---|---|
| FPC paper check not done (Task 8 Step 7: J301 reach, contact side, pin 1) | The VIEWE panel arrives with this order and VIEWE has not yet answered the adapter FPC questions. J301's mapping was checked against the VIEWE panel datasheet and the Waveshare J3 mapping only (panel pin N on connector pin 32 - N, pinned by a test); its position against the bezel notch comes from the enclosure model. | Before the first power-on with a panel attached: fold the adapter FPC through the bezel notch and check it reaches J301 without tension or twist; check its contacts face the board (FH26W is bottom contact) and its pin 1 mark is at J301's "31" end; with the panel plugged in and the board unpowered, check no short from DISP_3V3 (TP105) to GND. Then power from the bench supply on TP103 with a 150 mA limit, DISP_EN low, and raise DISP_EN while watching the current. |
| TPS63802 channel vias near pad 8 | The two GND vias in U103's centre channel sit 0.089 mm from pad 8's mask opening. They are tented and on the same net (GND) as pad 8, so a mask sliver lost there cannot short anything. JLC's DFM may still flag it. | Look at U103 under the loupe (bringup.md step 1). |
| Slow nets cross the In2 +3V3 boundary under the module | DISP_EN runs 12.0 mm along the 0.2 mm gap between the In2 GND and +3V3 pours at y 18.83; I2C_SDA, HALL_INT, TP_RST, EXP_A, EXP_B, IMU_INT1 and ESP_EN cross x = +-8.4 or y = 18.8. All are static or slow, In1 GND lies under every F.Cu run, and the B.Cu runs there sit over the +3V3 pour, which the module's decoupling ties to GND. QSPI and USB never leave GND reference. | Sensor bus rise time at 400 kHz (bringup.md step 5). |
| No fiducials on the board | The order selects edge rails with fiducials added by JLCPCB. The rails must be tab-routed, not V-cut: the outer pours and the stitching vias sit 0.3 to 0.5 mm from the edge, under the 0.4 mm JLC keeps from a V-cut line, and the outline is rounded. | File each tab nub flush before the board goes into the enclosure (it fits closely). |
| Part rotations and positions not yet seen in JLC's preview | The preview needs the owner's JLC sign-in. The five rotation offsets and the three position offsets (U201, J201, perch J1) above come from the footprint comparison, which assumes JLC's zero and origin are the EasyEDA footprint's and that JLC reads bottom rotations as the toolkit does; the private order notes list every polarised part with its expected orientation, and the positions of U201, J201 and J1. | Checked in the preview before paying. A change is a new value in design.toml and on the symbol (0, or "0,0" for a position, drops an offset; deleting the field would leave the footprint copy behind), then `hw_sync.py` and `hw_fab.py`, recorded in [ordering.md](ordering.md). A wrong bottom-side convention turns all seven polarised bottom parts at 90 or 270 by 180 at once; ordering.md lists them. |

### Analyses not run, and why

| Analysis | Reason |
|---|---|
| Datasheet extraction cache (`datasheets/extracted/`, the schematic analyzer's DS-002 warning) | Not built: the datasheets were read directly (table above) and are not committed. |
| Lifecycle status from DigiKey, Mouser or element14 | No API keys on this machine; LCSC gives stock but no lifecycle. The TI addenda and the stock check cover the order. |
| EMC pre-compliance measurement | No equipment; rev A is a prototype. |
| Board-level thermal simulation | The analyzer's point-source estimate and the hand figure for U101 are enough at under 1 W total. |

### Fabrication output notes

- The Fabrication Toolkit names the archive after the title block; `hw_fab.py` renames it to
  `owl-mainboard.zip` and restores `owl-mainboard.kicad_pro`, which pcbnew reorders when it saves
  the board.
- CPL coordinates are owl millimetres from the board's auxiliary origin (100, 100), Y up, at each
  footprint's anchor plus its `FT Position Offset` (U201, J201). Bottom rotations are the
  toolkit's (180 minus the KiCad rotation, plus its table offsets for SOT-23, JST_PH_S and TSSOP
  footprints), plus each part's `FT Rotation Offset`.
- 42 reference designators are hidden on the silkscreen for lack of room; the assembly drawing
  comes from the Fab layers.
