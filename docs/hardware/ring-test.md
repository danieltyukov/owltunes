# Ring test (rev A)

The ring test settles four things before the main board is ordered: which ring mechanism to use
(spec 7.2), how many magnets, the gap between the magnets and the TMAG5273, and whether the ring
hardware detunes the antenna (spec 15). The printed parts come from `enclosure/ring_test.py`.

## Parts to print (JLC3DP, MJF PA12, grey, standard finish, quantity 1 each)

| File | Purpose |
|---|---|
| face_bezel | Holds the glass (or a dummy disc, dropped in from the front and glued) and carries the bearing inner race |
| ring_a_bearing | Ring for the 6710ZZ bearing (bore 62.10, bearing glued) |
| ring_b_bushing | Ring for the printed bushing (bore 62.00) |
| bushing_sleeve | Replaces the bearing for variant B; O-ring groove for drag (59 x 1.5 O-ring: 0.8 percent stretch, 17 percent squeeze) |
| magnet_carrier_24, magnet_carrier_32 | 24 or 32 pockets for D3 x 2 mm magnets on a 56 mm circle; body 61.8 mm, fits both rings |
| sensor_jig | Base plate: holds the bezel and the SparkFun board where the PCB sensor will be; angle ticks every 10 degrees; antenna marker |
| jig_spacer_1mm, _2mm, _3mm | Under the SparkFun board: gap 4.5, 3.5, 2.5, 1.5 mm with 0, 1, 2, 3 mm |
| coupon_shaft | Stepped shaft 49.80 / 49.90 / 50.00 / 50.10 for the bearing bore |
| coupon_bore | Stepped bore 62.20 / 62.10 / 62.00 / 61.90 for the bearing outside, magnet pockets 2.95 to 3.25 |

## Buy separately

| Item | Quantity |
|---|---|
| 6710ZZ bearing, 50 x 62 x 6, steel | 2 |
| 6710 plastic bearing (POM races, glass balls), 50 x 62 x 6 | 1 |
| N52 disc magnets D3 x 2 mm, axially magnetised | 80 |
| O-ring 59 x 1.5 mm NBR 70 (ID 59, cross-section 1.5, OD 62) | 4 |
| Damping grease (heavy, for camera focus rings) | 1 small tube |
| M2 x 10 screws and M2 hex nuts | 3 each |
| Cyanoacrylate glue | 1 |
| SparkFun Linear 3D Hall-Effect Sensor TMAG5273 (Qwiic), SEN-23880, and a Qwiic cable | 1 |
| Any ESP32-S3 board with a WROOM-1 PCB antenna (for example ESP32-S3-DevKitC-1) | 1 |

## Wall thickness

Walls follow JLC3DP's MJF nylon guideline: 1.0 mm for structural walls, 0.8 mm only for
non-critical features (the glass pocket wall in the bezel is 0.8 mm). Separately printed fits keep
the clearances listed in `enclosure/owl_params.py`. The bezel's glass pocket is 48.30 mm for the
48.16 mm glass (0.07 mm per side): if the glass does not drop in, open the pocket with a scraper
or fine sandpaper.

## Assembly

1. Magnets: hold a reference magnet; every pocket with a bump behind it gets a magnet that the
   reference attracts, every other pocket one that it repels, so polarity alternates. A drop of
   glue in each pocket.
2. Variant A: slide a 6710ZZ onto the bezel seat from the back until it stops on the lip (a drop
   of glue if loose). Press ring A onto the outer race from the front until the lip touches it.
   Variant B: glue the bushing sleeve onto the seat, fit the O-ring in its groove, grease the
   sleeve and push ring B on from the front.
3. Push a magnet carrier into the ring from the back until its flange touches the ring.
4. Screw the bezel lugs to the jig with M2 x 10 screws, nuts in the hex pockets underneath.
5. SparkFun board into the jig pocket, parts side up, the chosen spacer under it. The board is
   turned so the TMAG5273 chip (not the board centre) sits at the sensor position: connector J1
   faces the centre and J2 faces outwards, where the cable slot is.

## Measurements

| Id | What | How |
|---|---|---|
| M1 | Feel and play | Turn each variant slowly and fast; note smoothness and any cogging. Axial wobble: calipers from the jig face to the ring's front at 0, 90, 180, 270 degrees while pressing the ring at the opposite side; record max minus min |
| M2 | Field | For each carrier and spacer: log with SparkFun's Arduino library Example1 at about 100 Hz, ring still for 2 s, then one turn from the 0 tick back to 0. Run `uv run --project enclosure python enclosure/ring_analysis.py LOG --magnets N` |
| M3 | Cogging | With the steel bearing and with the plastic bearing: does the ring snap to positions? |
| M4 | RSSI | Tape the ESP32 board so its antenna sits in the marked rectangle. Log RSSI to the access point (3 m away, same spot) for 30 s each: no ring, ring A steel with magnets, ring A plastic bearing with magnets, ring B. Average each |
| M5 | Fits | Which coupon step the bearing stops at (inside and outside) and which magnet pocket holds a magnet without glue |

## Acceptance

- Ring mechanism: axial wobble at the rim at most 0.3 mm, no cogging a user can feel, and an RSSI
  drop of at most 3 dB against no ring. Prefer A with a steel bearing if it passes RSSI, else A
  with the plastic bearing, else B.
- Magnet count: electrical cycles equal to half the magnet count; prefer the count with the
  smaller cogging and a Z to Y amplitude ratio nearer 1.
- Gap: the smallest gap whose peak field stays under 120 mT (TMAG5273A2, 133 mT range) and over
  15 mT. The product needs a gap of at least 3.0 mm (board front 0.3 mm behind the 1.0 mm carrier
  flange, magnets flush with the carrier's rear face). The polarity bumps on the test carriers
  reach the board plane, so the product magnet carrier is built with `bumps=False`.
- If no variant passes, the EC11 encoder fallback is used through J202 (spec 7.2) and the
  decision is recorded before the PCB order.

## Decision record

| Item | Result | Value written to owl_params.py |
|---|---|---|
| Ring mechanism | | |
| Bearing material | | |
| Magnet count | | MAGNET_COUNTS |
| Hall gap (mm) | | HALL_GAP_NOMINAL |
| Peak field at that gap (mT) | | |
| TMAG5273 variant and range | | design.toml U302 |
| RSSI no ring / A steel / A plastic / B (dBm) | | |
| Bearing seat diameter | | BRG_SEAT_D |
| Ring A bore | | RING_A_BORE_D |
| Magnet pocket | | MAG_POCKET_D |
| Encoder fallback needed | | |
