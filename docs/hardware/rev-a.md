# Hardware rev A

Rev A is the first OwlTunes board set: the owl main board (4 layers, JLCPCB assembled on both
sides), the perch board with a snap-off dock-pad section for the owl's back cover, enclosure v1
and perch v1 (MJF PA12). Spec: `docs/design/2026-10-04-owltunes-system-design.md`, sections 7 and 8.

Status on 12 October 2026: both boards are placed, routed and reviewed (ERC 0, DRC 0 with
schematic parity, [rev-a-review.md](rev-a-review.md)), and their fabrication files are ready
(`tools/hw/hw_fab.py`; what to order is in [ordering.md](ordering.md)). Enclosure v1 and perch v1
are drawn and reviewed, and the main board's fit check against enclosure v1 finds no clash. Nothing
is ordered yet. The ring test runs when the parts are delivered, so until then the magnet count,
the ring variant (A with the 6710 bearing, B with the printed bushing) and the 3.0 mm Hall gap are
provisional.

The firmware pin map is `firmware/main/board_owltunes_reva.h` (see [pinmap.md](pinmap.md)). It
is a header only for now: rev A board support arrives with the P3 board selection.

## Blocks

```
 USB-C --- USBLC6 --- 22R --- ESP32-S3 USB (GPIO19/20)
   |  CC: 5.1k x2
 VBUS_USB --TVS-- Schottky --+              TS: RT101 10k NTC
                             +-- VIN_CHG -- BQ24073 --- VSYS --- TPS63802 --- +3V3 (always on)
 VBUS_DOCK -TVS-- Schottky --+   (ILIM 0.42 A)  |  ICHG 0.27 A    (3.30 V)        |
   (J303 from the dock pads)                    BAT --- JST PH 2-pin: 1S LiPo       +-- TPS22917 -- DISP_3V3
                                                |                                    |    (AMOLED, touch)
                                          MAX17048 (VBAT)                            +-- ESP32-S3-WROOM-1-N16R8
 Sensor I2C (+3V3): TMAG5273A2 0x35, MAX17048 0x36, LIS2DW12 0x19, OPT3001 0x44, DRV2605L 0x5A
 Touch I2C: ESP32-S3 side on DISP_3V3 --- U305 LSF0204 --- panel side on DISP_1V8 (U306 from DISP_3V3):
 CST820 0x15.  QSPI (FSPI IO_MUX pins 9 to 14, 40 MHz): CO5300 AMOLED.
```

## Mechanical stack (depth behind the cover glass front, mm)

Values from `enclosure/owl_params.py` and `enclosure/owl_v1.py`.

| Item | Depth |
|---|---|
| Ring and bezel front lips | -1.3 to 0 |
| Cover glass, OCA, panel and foam (2.07), parts on the folded flex (1.2) | 0 to about 3.3 |
| Bearing 6710 (ring A) or printed bushing sleeve (ring B) | 0 to 6.0 |
| Magnet carrier (magnets flush with its rear face at 9.2, flange 9.2 to 10.2) | 6.2 to 10.2 |
| Main board (TMAG5273 on the back side, Hall element 3.0 mm behind the magnets) | 10.5 to 11.5 |
| Battery foam | 11.5 to 12.7 |
| Battery (8 mm: an 803030 class cell in a cavity drawn for an 803040) | 12.7 to 20.7 |
| Back cover | 20.7 to 22.2 |

Outside size 66 x 84 x 23.5 mm (spec 7.1: about 66 x 84 x 22). Every 0.1 mm added to the Hall
gap adds 0.1 mm of depth.

## Off-board parts at the battery

Bought separately and fitted at assembly ([assembly.md](assembly.md) steps 6 and 8):

- Battery: a 2-wire 1S LiPo of the 803030 class (8 x 30 x 30 mm) with a protection circuit and a
  JST PH 2.0 2-pin plug: efaso 803030 740 mAh, or EEMB 803030 700 mAh if its plug is confirmed as
  PH 2.0. The cavity is drawn for an 803040 (8 x 30 x 40 mm); the shorter cell sits lead end up
  against a 1 mm foam-tape end stop on the cover ([assembly.md](assembly.md) step 8). See
  Protection and known limits for the polarity and the charge current.
- Thermal gap pad: a piece of soft, electrically insulating silicone gap pad, about 5 x 5 mm,
  1.5 mm thick (it compresses into the 1.2 mm battery gap), 1 to 3 W/mK. It goes on the back of
  the board, centred on RT101's copper patch: the 4.5 x 3 mm copper rectangle under the solder
  mask at owl (-0.4, -9.5), 4.5 mm below the centre of U303 (the 2 x 2 mm LIS2DW12 on the
  board's centre line), with RT101 just past its end (on the right, seen from the back). The
  cell presses on it, so the patch, and RT101 through its neck, follow the cell more closely
  than across the air gap alone. With a 1.5 W/mK pad RT101 should read about half way from the
  board's temperature to the cell's (an estimate; `tools/hw/hw_route.py` bat_ntc has the
  numbers), against a few percent without the pad.

## Calculations

Charger (BQ24073, TI SLUS810N section 8.5):
- Fast charge: ICHG = KISET / RISET = 890 / 3300 = 0.270 A (KISET 797 to 975 and R101 1 %: 0.239
  to 0.298 A, SLUS810N p. 13). R101 = 3.3k keeps the worst case under 0.5 C of the 700 mAh fallback
  pack (0.35 A needs RISET of at least 975 / 0.35 / 0.99 = 2.81k; 2.8k to 3k are JLC Extended, 3.3k
  is the nearest Basic value): 0.43 C worst case on 700 mAh, 0.40 C on 740 mAh.
- Input limit: IIN = KILIM / RILIM with R102 = 3.6k: 1330, 1525 and 1720 A-ohm (minimum,
  typical, maximum) give 0.369, 0.424 and 0.478 A (0.483 A with the resistor 1 % low), so even the
  worst case stays inside USB 2.0 default power (500 mA), which the firmware declares. USB 2.0
  default power is the target because the board has plain 5.1k Rd on CC1 and CC2 and does not
  read CC, the ESP32-S3 is a USB 2.0 device, and VIN-DPM is off in ILIM mode. A 3.3k ILIM would
  reach 0.52 A at its worst case.
- ICHG (0.27 A) is below the input limit (0.369 A at its minimum), so the cell charges at ICHG
  while the system draws less than the difference (about 0.1 to 0.15 A from the input); a heavier
  load takes its share first and the charge current drops, with the safety timers slowed to match
  (SLUS810N p. 28).
- EN2 is tied high through R103, so firmware chooses between the ILIM limit (CHG_SUSPEND low)
  and input suspend (CHG_SUSPEND high).
- Precharge 88 / 3300 = 27 mA; termination 10 % of ICHG = 27 mA; timers 30 min and 5 h (TMR open;
  4 to 6 h over tolerance, SLUS810N p. 13). A 740 mAh cell takes roughly 3 h at 0.24 to 0.30 A
  (an estimate: constant current to about 80 %, then the taper), inside the fast-charge timer's
  4 h minimum; a load that cuts the charge current slows the timer to match.
- NTC: TS sources 75 uA (72 to 78 uA) into RT101, a 10k NTC on the board (Sunlord
  SDNT1005X103F3950FTF: B25/50 3950 K, 1 % on R25 and on B), so TS reads 0.75 V at 25 C. The TS
  thresholds are set for the 103AT-2 curve (0 to 50 C, SLUS810N 9.3.6); the steeper B 3950 curve
  narrows the window, which resistors on TS cannot do (same section). On the B25/50 model
  charging stops above 47.2 C (VHOT 0.30 V, 4.0k) and resumes below 44.7 C; it stops below
  +3.5 C (VCOLD 2.1 V, 28.0k) and resumes above 6.5 C. With the VHOT, VCOLD and bias tolerances
  the hot cut-off lies between 43.7 and 51.0 C and the cold one between +1.8 and +5.2 C; RT101's
  own 1 % tolerances widen that to 43.2 to 51.5 C and +1.4 to +5.6 C. The alternate's published
  R-T table (KUU KNTC0402/10KF3950, also B25/50 3950 K) gives the same hot points and puts the
  cold ones about 0.4 C lower (cut-off +3.1 C, release 6.2 C). An open TS reads above VCOLD, so
  it counts as cold.
- RT101 reads the board, not the cell: it sits on the back under the middle of the cell, which
  is 1.2 mm behind the board, 30 mm from U101 and 19 mm from U103. In fast charge U101's heat
  reaches it through the planes, so it reads warmer than the cell: charging stops while the cell
  is still a few degrees below the hot cut-off, and a cell a few degrees below the cold cut-off
  still charges. The charge temperature window is approximate.
- Charging may pause in a warm room (the hot cut-off can be as low as 43.2 C and RT101 reads
  warm); it resumes about 2.5 C lower, and the safety timers pause with it (SLUS810N 9.3.6).
- Cells are often rated for charging from 0 to 45 C. The cold cut-off stays above 0 C at its
  worst case; the hot one is 47.2 C nominal and up to 51.5 C. Check the bought cell's limit.
- Dissipation in fast charge: (VIN - VOUT) x IIN + (VOUT - VBAT) x ICHG with OUT at 4.4 V and
  about 4.6 V at IN. Typical (ICHG 0.270 A, no system load): 0.2 x 0.27 + 0.9 x 0.27 = 0.30 W at
  VBAT 3.5 V, 0.43 W at VBAT 3.0 V where fast charge starts; worst case about 0.51 W (ICHG 0.298 A
  at VBAT 3.0 V, the input at its 0.478 A limit with the system load). The charger regulates at 125 C junction; U101
  is kept out of the battery footprint.
- Schottky PMEG2020EH: under 0.38 V at the input limit, so the charger sees about 4.6 V from a
  5.0 V source.
- IN capacitance: C101 4.7 uF (BQ24073 IN accepts 1 to 10 uF) keeps the capacitance a USB host
  sees through D101 under the USB limit of 10 uF.

Buck-boost (TPS63802, TI SLVSEU9D section 10):
- VOUT = 0.5 V x (1 + 560k / 100k) = 3.300 V (3.21 to 3.39 V with 1 % resistors and the 1 %
  reference); divider current 3.3 V / 660k = 5.0 uA. R108 100k is at TI's 100k maximum for R2; TI's
  511k and 91k pair gives 3.31 V if more margin is wanted. Never trim the output up: DISP_3V3 is
  already at the top of the panel's IOVCC range.
- Peak inductor current (TI equations 1 and 2, 0.8 A out, 2.1 MHz, 0.47 uH, 90 % efficiency):
  VIN 3.0 V: D = 0.091, Ipk = 0.98 + 0.14 = 1.12 A; VIN 2.5 V: D = 0.242, Ipk = 1.17 + 0.31 =
  1.48 A. The DFE201612E-R47M saturates at 5.5 A.
- PG to ESP_EN: R205 47k pull-up, R212 4.7k from PG, C203 220 nF. With PG low it sinks at most
  0.70 mA (TPS63802 PG is specified up to 1 mA) and holds EN at 0.30 V or less against the
  ESP32-S3's 0.74 V reset threshold. Release time constant 47k x 220 nF = 10.3 ms (Espressif asks
  for 10 ms); glitch filter about 0.94 ms.

Load switch (TPS22917, TI SLVSDW8B): CT 1 nF to VIN gives a slew of about 1.8 mV/us at 3.3 V, so
DISP_3V3 reaches 3.3 V in about 1.9 ms (turn-on time 3.8 ms at 3.6 V). The inrush is about 50 mA
with all VOUT capacitors: the panel's own (about 20 uF) plus C111, C112, C301 and C302 (14.9 uF
nominal, about 9 uF at 3.3 V bias). QOD is tied to VOUT for the internal 150 ohm discharge.

Dock detection: DOCK_DET = 3.3 V x (1k + 10k) / (100k + 1k + 10k) = 327 mV on the perch,
3.3 V undocked, 33 mV with the pad shorted to GND. Docked means 150 to 600 mV and CHG_PGOOD low.
The divider draws 30 uA, only while docked (on external power).

32.768 kHz crystal: 12.5 pF load, so C204 and C205 = 2 x (12.5 - 3.5) = 18 pF (C0G).

## Power budget (spec 8.3) against rev A

| State | Spec | Rev A estimate | Basis |
|---|---|---|---|
| Screen on, Wi-Fi active | 110 to 180 mA | about 105 to 180 mA | ESP32-S3 Wi-Fi modem sleep 40 to 60 mA, panel 30 to 75 mA (VIEWE: 75 mA full red), touch 1.9 mA typical (plus 18 uA in R310 while the panel is on), at 3.3 V through the 90 % buck-boost |
| Screen off, Wi-Fi associated | about 3 mA | about 3 mA | Espressif light sleep with DTIM 3, 32.768 kHz crystal fitted |
| Wi-Fi off, BLE advertising | 0.5 to 1 mA | about 0.5 to 1 mA | Espressif BLE light sleep figures |
| Deep sleep | about 30 uA | about 44 uA | below |
| Typical day (1 h use) | about 6 days | 3.5 to 5 days | 1 h at 120 to 180 mA, 15 min hot standby at 3 mA, deep sleep the rest; about 630 mAh usable of the 740 mAh cell (595 of a 700 mAh one) |

Deep sleep, battery side: TPS63802 quiescent 11 uA; BQ24073 battery sleep 4.3 uA; MAX17048
hibernate 3 uA; pack protection about 3 uA; and the 3.3 V loads (ESP32-S3 deep sleep 8 uA,
DRV2605L standby 4.1 uA, TPS63802 divider 5.0 uA, TMAG5273 wake-up-and-sleep at 100 ms about 2 uA,
LIS2DW12 low-power about 1 uA, OPT3001 shutdown 0.3 uA = 20.4 uA at 3.3 V, 22.7 uA from the cell at
80 % light-load efficiency). Total about 44 uA: 630 mAh usable lasts about 1.6 years. The largest
single item is the TPS63802 quiescent current; measure all of this at bring-up.

These figures assume every pull-up is idle: the buttons open, DOCK_DET undocked, and an encoder
on J202 resting open at its detents. Each closed J202 channel draws 0.33 mA through its 10k
pull-up, which would dominate the sleep current.

## Firmware rules from the hardware

These are also written in `firmware/main/board_owltunes_reva.h`.

- Panel power-down: display off and sleep-in, wait 120 ms; drive LCD_RST and TP_RST low; hold
  LCD_CS, LCD_CLK and LCD_D0 to D3 low or high impedance and turn off the internal pull-ups on
  TP_SDA, TP_SCL, TP_INT and LCD_TE; keep those levels through deep sleep with the pad hold
  (GPIO38 to 40, 47 and 48 are not RTC pads); then DISP_EN low. Power-up: DISP_EN high, wait
  10 ms, release the resets.
- IMU_INT1: set the LIS2DW12 interrupt push-pull and active low (H_LACTIVE = 1) before ext1 is
  armed, and again after any LIS2DW12 reset (it comes out of reset driving INT1 low).
- HALL_INT: use the TMAG5273 latched interrupt mode; the pulse mode is only 10 us wide.
- ext1 ANY_LOW wakes at once if a masked pin is already low, so arm only the pins that read high:
  on external power drop CHG_PGOOD and DOCK_DET, and clear a latched HALL_INT by addressing the
  TMAG5273 first.
- DRV2605L: EN is tied high, so idle it with the STANDBY bit and never let its VDD drop while the
  I2C bus is up.
- Sensor bus: 4.7k pull-ups. Measure the rise time at 400 kHz at bring-up; if it is too slow, run
  at 100 kHz or fit 2.2k pull-ups (not lower).
- USB: any USB configuration descriptor the firmware sends declares 500 mA maximum power
  (`OWL_USB_MAX_POWER_MA`).
- Docked only when DOCK_DET reads 150 to 600 mV and CHG_PGOOD is low.

## Protection and known limits

- The pack is a 2-wire 1S LiPo of the 803030 class (8 x 30 x 30 mm; efaso 803030 740 mAh or EEMB
  803030 700 mAh) with a protection circuit and a JST PH 2.0 2-pin plug. J101 is a 2-pin JST PH,
  S2B-PH-SM4-TB (pin 1 VBAT, pin 2 GND). A pack's own NTC wire, if it has one, is not used: the
  board's RT101 is on TS.
- Charge current against the smaller cell: ICHG is 0.270 A typical, 0.298 A worst case (R101
  3.3k): 0.40 C of 740 mAh and 0.43 C of 700 mAh at worst, so any cell rated for 0.5 C charging
  or more is fine.
- J101 (battery) has no reverse-polarity protection. Many packs are wired the other way round,
  so check that the plug's red wire lands on the silkscreen `+` (pin 1, with the dot) before
  plugging it in; the housing can be re-pinned (see [assembly.md](assembly.md)).
- TD (U101 pin 15) is tied to GND, so an open TS reads as cold (SLUS810N 9.3.5.3 and 9.3.6): with
  RT101 open or missing nothing charges, and CHG stays low as if charging while no current flows.
  The BQ24075 alternate listed in `design.toml` behaves the same.
- U202 (USBLC6-2SC6) pin 5 (VBUS) is left unconnected so the ESP32-S3's default D+ pull-up cannot
  back-feed the receptacle's VBUS through the upper steering diode when no cable is present. The
  USBLC6 still clamps through its internal rail; D201 (SMF5.0A) protects VBUS_USB and D301 protects
  VBUS_DOCK.
- The TPS22918 alternate for U104 needs its reverse-current behaviour confirmed before it is
  fitted.
- The U0TXD 499 ohm series resistor that Espressif recommends is inside the module (WROOM-1
  datasheet figure 8-1, R3), so the board has none.

## Decisions and deviations from the spec

| Item | Spec | Rev A | Why |
|---|---|---|---|
| Panel supplies | VCI and IOVCC | VCI, IOVCC, VCI_EN, VBAT, TP_3.3V all on DISP_3V3 | VIEWE panel has a VBAT pin for its own boost; the Waveshare kit feeds it 3.3 V |
| I2C | one bus implied | two buses | touch is powered off with the panel, and it sits on its own 1.8 V side behind U305; the CST820 (0x15) no longer shares an address with the DRV2605L (0x5A), so the second bus is for power-down and level, not for an address clash |
| Touch level | touch on DISP_3V3 | CST820 at 1.8 V: U306 XC6206P182MR makes DISP_1V8 from DISP_3V3, U305 LSF0204 translates SDA, SCL, INT and RST (TP_*_1V8, 4.7k and 10k pull-ups to DISP_1V8) | the CST820 at 0x15 must see 1.8 V (VIEWE drawing note). Both new parts are JLC Extended and have no Basic or Preferred equivalent. With DISP_3V3 off every translator pin is high impedance, so no GPIO can back-power the touch controller. Fallback: fit R315 (0R, not assembled) to put DISP_1V8 at 3.3 V |
| J301 position | top edge of the panel, rotation 180 | owl (-5.00, 4.22), rotation 270, front side | VIEWE's standard adapter FPC (USD 0.80) reaches it with one U-turn and one S-bend; see Display adapter route |
| Panel QSPI clock | 80 MHz | 40 MHz | the panel allows 50 MHz for writes; the board runs the QSPI at 40 MHz |
| TMAG5273 | on the PCB | back side of the board | lets the board front sit 0.3 mm behind the carrier flange |
| Dock pads | on the main board | separate dock-pad board, cabled to J303 | the main board is about 11 mm in front of the back surface |
| Antenna keep-out | 15 mm from the ring | not reachable in 66 x 84 mm | to be measured in the ring test (RSSI with and without the ring stack); WROOM-1U fallback on the same pads |
| Owl depth | about 22 mm | 23.5 mm | bearing plus a 3.0 mm sensor gap |
| Battery NTC | 10k NTC in the pack, JST PH (8.1) | 2-wire pack on a 2-pin JST PH; RT101 (10k NTC) on the board under the cell | cheap off-the-shelf packs are 2-wire, and the BQ24073 does not charge with TS open. Cost: RT101 reads the board under the cell, so the charge temperature window is approximate (a few degrees warm in fast charge) |
| Battery size | 1S LiPo about 1000 mAh (803040) | 803030 class, 740 mAh (efaso; EEMB 700 mAh as the fallback) in the 803040 cavity, held by a foam end stop | the only listings found with a stated JST PH 2.0 plug that fit the cavity: the efaso 803040 variant has a 1.0 mm pitch plug, and an 803040 whose protection board sits outside its 40 mm is too long. Cost: about 26 % less capacity, a typical day of 3.5 to 5 days instead of about 6. An 803040 with a PH 2.0 plug and its protection board inside the 40 mm fits the same cavity later |
| Charger input limit | not stated | 0.424 A typical, 0.478 A worst case (R102 3.6k) | USB 2.0 default power without CC sensing; faster charging needs CC sensing in rev B |
| Charge current | not stated | 0.270 A typical, 0.298 A worst case (R101 3.3k) | controller ruling, 12 October 2026: at most 0.5 C of the 700 mAh fallback pack in the worst case. Cost: a full charge takes roughly 3 h instead of about 2 h at the earlier 0.445 A |
| Cover glass retention | not stated | adhesive: glass on an adhesive ring, 1.3 mm retainer ring glued into the lip opening | a snap does not fit the 1.3 mm lip with the bearing behind it. Owner review point: the glass could come loose if a glue joint fails in a drop; a mechanical lock (a taller lip or a bayonet) is a v2 item |
| Perch USB-C | on the back of the perch (7.3) | right side of the back rest, the plug enters along +X | J1 is an edge-mount receptacle in the tilted rest plane and the perch board is Economic PCBA (top side only). Owner review point: a back exit needs a vertical receptacle on the board's bottom side, hand-soldered or with Standard PCBA, plus a boss on the rest's back; rev B can move it. The side channel takes the largest Type-C overmold (12.35 x 6.5 mm) |

## Display adapter route

The panel's standard adapter FPC (31 contacts at 0.30 mm, 9.60 mm wide, 0.20 mm thick, 24.148 mm from
the panel connector's front face to the end of the fingers, 5.00 mm stiffeners at the finger ends)
plugs into the panel connector, makes a U-turn towards 9 o'clock over the H2 screw head, and an
S-bend down to J301 at owl (-5.00, 4.22). Lengths along the flex's mid-plane, bend radius 2.0 mm
(10 x thickness), s = distance from the display centre towards 9 o'clock:

| Segment | Length (mm) | Note |
|---|---|---|
| Inside the panel connector | 2.50 | not counted: the 24.148 starts at the connector face |
| Plug-end stiffener, straight out | 2.50 | s 14.96 to 17.46, depth 2.8 |
| U-turn outward and back, R 2.0 | 6.28 | depth 2.8 to 6.8, contacts now towards the board |
| Straight run over the H2 screw head | 3.6 to 4.1 | depth 6.8 |
| S-bend down, two arcs R 2.0 of 78.5 degrees | 5.48 | depth 6.8 to 10.0 |
| Lead-in on the board, last 2.50 is the stiffener | 2.5 to 3.0 | to J301's entry face |
| Inside J301 | 2.50 | |
| Sum | 23.38 | the rows below the first, with the straight run and the lead-in together 6.62 wherever the S-bend sits (4.1 with 2.5, down to 3.6 with 3.0); adapter 24.148: 0.77 mm slack, taken up by the U-turn growing outward |

`enclosure/tests/test_pcb_contract.py` (`test_display_adapter_reaches_j301`) computes this from the
constants in `enclosure/owl_params.py`: 0.766 mm of slack nominal and 0.016 mm at the tolerance
corner (connector face 0.6 mm further out, adapter 0.15 mm short). The S-bend may start anywhere in
a window of s 13.34 to 13.85. The U-turn apex is at radius 21.89 mm (the bezel bore allows 23.1) and
its underside clears the H2 screw head by 0.30 mm.

Two inputs are estimates, because VIEWE does not dimension them: the panel connector's front face
(taken as 14.96 mm from the centre, covered 14.5 to 15.55) and the adapter's mid-plane depth at the
panel connector, 2.8 +- 0.2 mm. The route is sensitive to both:

- At 2.6 mm depth the stacked worst corner (connector face 0.6 mm further out, adapter 0.15 mm
  short) leaves -0.15 mm of slack, so the adapter would be too short.
- At 3.0 mm depth the clearance over the H2 screw head drops to 0.10 mm. A wafer-head M2 at H2 is
  the fallback.

The physical check in the open items below settles both.

## Open items checked at bring-up

- Adapter fit check, before the board is ordered (about 10 minutes). Build the route with a real
  VIEWE adapter, or with a 1:1 paper strip 9.6 mm wide and 26.65 mm long (24.148 + 2.50) with 5.00 mm
  stiffener ends, against a 1:1 print of the board front around J301 and the printed bezel with the
  H2 screw fitted. The print is one A4 page; make it from the repository root with

  ```
  kicad-cli pcb export pdf --mode-single --scale 1 --ibt \
    --drawing-sheet hardware/owl-mainboard/j301-fit-check.kicad_wks \
    -l Edge.Cuts,F.Cu,F.Silkscreen,F.Fab,F.Courtyard,User.Comments \
    -o private/orders/j301-adapter-check-1to1.pdf hardware/owl-mainboard/owl-mainboard.kicad_pcb
  ```

  and print it at actual size, not fit to page. Check the scale on paper before use: the two bars
  on the page are 10 mm, and the board outline is 61.8 mm wide. Measure the panel connector's
  front face from the display centre and the adapter's depth at it. Confirm 0 to 1.4 mm of slack at
  J301 x -5.00; otherwise move J301 by the difference before ordering the board. The panels and
  adapters can be ordered first and this check run before the board order, or everything can be
  ordered at once and the computed slack relied on (see Display adapter route).
- Touch I2C level: the CST820 at 0x15 runs at 1.8 V behind U305 (resolved in the design). If the
  scan at bring-up does not find 0x15, fit R315 (0R, DISP_3V3 to DISP_1V8) before anything else.
  That puts the bus at 3.3 V on both sides of U305, outside the LSF0204's translation conditions, so
  it is a lab trial only.
- Open questions to VIEWE: the order code of the 48.16 mm glass version; the touch INT and RST
  levels; the panel connector's front face and the adapter stiffener; and the VBAT pin level.
- Panel VBAT at 3.3 V: the VIEWE pin table gives VBAT 3.7 to 4.5 V and its application circuit
  3.3 to 5.5 V; the Waveshare kit runs it at 3.3 V. Asked VIEWE (the VBAT pin level). If the panel
  misbehaves, feed VBAT from VSYS with a bodge wire.
- Sensor bus rise time at 400 kHz with the 4.7k pull-ups.
- RT101 against the cell: with the gap pad fitted (Off-board parts), during a USB charge (about
  0.27 A) from about 3.5 V, compare RT101's temperature (from the TS
  voltage, 75 uA x R) with a thermocouple taped to the cell. If it reads more than a few degrees
  off, check that the pad touches both the patch and the cell, or try a 3 W/mK pad. Check the
  hot cut-off (47.2 C nominal, 43.2 to 51.5 C worst case) against the bought cell's charge
  temperature limit.
- RTC crystal drift (18 pF load capacitors).
- Deep-sleep current against the 44 uA estimate, and DISP_3V3 near 0 V with the panel off (no
  back-powering through an I/O pin).
- Ring sensor offset with the dock magnets near (spec 15: recalibrate on dock).
- Ring test results: magnet count, ring A or B, the Hall gap, and the WROOM-1 or WROOM-1U choice
  from the RSSI with and without the ring stack.
