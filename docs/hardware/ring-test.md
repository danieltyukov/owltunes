# Ring test (rev A)

The ring test settles four things: which ring mechanism to use (spec 7.2), how many magnets, the
gap between the magnets and the TMAG5273, and whether the ring hardware detunes the antenna
(spec 15). It runs when the parts arrive: the rev A order buys both ring variants and both magnet
carriers ([ordering.md](ordering.md)). The printed parts come from `enclosure/ring_test.py`.

## Parts to print (JLC3DP, MJF PA12, grey, standard finish, quantity 1 each)

| File | Purpose |
|---|---|
| face_bezel | Carries the bearing inner race; its front face, flush with the bearing's, is the ledge the glass (or a dummy disc) rests on with 0.2 mm tape |
| ring_a_bearing | Ring for the 6710ZZ bearing (bore 62.10, bearing glued) |
| ring_b_bushing | Ring for the printed bushing (bore 62.00) |
| bushing_sleeve | Replaces the bearing for variant B; O-ring groove for drag (59 x 1.5 O-ring: 0.8 percent stretch, 17 percent squeeze) |
| magnet_carrier_24, magnet_carrier_32 | 24 or 32 pockets for D3 x 1 mm magnets on a 56 mm circle, opening in the rear face; body 61.8 mm, fits both rings; the flange sits beside the pockets |
| sensor_jig | Base plate: holds the bezel and the SparkFun board where the PCB sensor will be; angle ticks every 10 degrees; antenna marker |
| jig_spacer_1mm, _2mm, _3mm | Under the SparkFun board: gap 4.7, 3.7, 2.7, 1.7 mm with 0, 1, 2, 3 mm (2 mm gives the product gap) |
| coupon_shaft | Stepped shaft 49.80 / 49.90 / 50.00 / 50.10 for the bearing bore |
| coupon_bore | Stepped bore 62.20 / 62.10 / 62.00 / 61.90 for the bearing outside, magnet pockets 2.95 to 3.25 (1.0 deep) |

## Buy separately

| Item | Quantity |
|---|---|
| 6710ZZ bearing, 50 x 62 x 6, steel | 2 |
| N52 disc magnets D3 x 1 mm, axially magnetised | 80 |
| O-ring 59 x 1.5 mm NBR 70 (ID 59, cross-section 1.5, OD 62) | 4 |
| Damping grease (heavy, for camera focus rings) | 1 small tube |
| M2 x 10 screws and M2 hex nuts | 3 each |
| Cyanoacrylate glue (magnets, ring-test parts) | 1 |
| Two-part epoxy (bearing and bushing sleeve on the bezel seat) | 1 |
| SparkFun Linear 3D Hall-Effect Sensor TMAG5273 (Qwiic), SEN-23880, and a Qwiic cable | 1 |
| Arduino Nano ESP32 (NORA-W106, PCB antenna; the owner's), for the RSSI runs (M4) | 1 |

## Wall thickness

Walls follow JLC3DP's MJF nylon guideline: 1.0 mm for structural walls, 0.8 mm only for
non-critical features (no ring test part needs the thinner class). Separately printed fits keep the
clearances listed in `enclosure/owl_params.py`. The bezel has no glass pocket: VIEWE supplies only
the 52.6 mm glass (reply of 14 October 2026: the 48.16 mm glass is discontinued), which is wider
than the bearing's bore, so it rests on 0.2 mm tape on the bezel's front face, 0.2 mm in front of
the inner race, inside the ring lip (53.6 mm, 0.5 mm clear of the glass edge).

## Assembly

1. Magnets: hold a reference magnet; every pocket with a bump behind it gets a magnet that the
   reference attracts, every other pocket one that it repels, so polarity alternates. A drop of
   glue in each pocket.
2. Cover a flat plate with release film (PTFE film or packing tape) and lay the bezel face down
   on it. Nothing stands in front of the bearing, so the plate sets it flush with the bezel's front
   face. Variant A: spread two-part epoxy thinly on the bezel seat (none on the shields) and slide a
   6710ZZ onto it from the back until it touches the plate. Before the epoxy sets, lift the bezel
   off the film and wipe the bezel's front face and the inner race's front face clean (they carry
   the glass tape), then lay it back face down and let the epoxy set (it holds the bearing in both
   directions). Press ring A onto the outer race from the front until the lip touches it. Variant
   B: glue the bushing sleeve onto the seat the same way, fit the O-ring in its groove, grease the
   sleeve and push ring B on from the front.
3. Push a magnet carrier into the ring from the back until its flange touches the ring's rear face.
   The flange sits beside the magnets, flush with them.
4. Screw the bezel lugs to the jig with M2 x 10 screws, nuts in the hex pockets underneath.
5. SparkFun board into the jig pocket, parts side up, the chosen spacer under it. The board is
   turned so the TMAG5273 chip (not the board centre) sits at the sensor position: connector J1
   faces the centre and J2 faces outwards, where the cable slot is.

## Measurements

| Id | What | How |
|---|---|---|
| M1 | Feel and play | Turn each variant slowly and fast; note smoothness and any cogging. Axial wobble: calipers from the jig face to the ring's front at 0, 90, 180, 270 degrees while pressing the ring at the opposite side; record max minus min |
| M2 | Field | For each carrier and spacer: log with SparkFun's Arduino library Example1 at about 100 Hz, ring still for 2 s, then one turn from the 0 tick back to 0. Run `uv run --project enclosure python enclosure/ring_analysis.py LOG --magnets N` |
| M3 | Cogging | With the steel bearing (ring A) and with the bushing (ring B): does the ring snap to positions? |
| M4 | RSSI | Tape the Nano ESP32 so its PCB antenna sits in the marked rectangle. Log RSSI to the access point (3 m away, same spot) for 30 s each: no ring, ring A (steel bearing) with magnets, ring B with magnets. Average each; the result is each ring's drop against no ring (a relative figure, so the Nano's antenna stands in for the WROOM-1's) |
| M5 | Fits | Which coupon step the bearing stops at (inside and outside) and which magnet pocket holds a magnet without glue. On the 6710ZZ in hand: the inner race land's outside diameter (BRG_INNER_RACE_OD, estimated 53.6) must exceed the largest glass edge, 52.75, so the glass overhang sits over the stationary race; and the shields must not stand proud of the race's front face. If a shield does, the glass needs tape thicker than 0.2 mm by that much (GLASS_TAPE_T) |

## Acceptance

- Ring mechanism: axial wobble at the rim at most 0.3 mm, no cogging a user can feel, and an RSSI
  drop of at most 3 dB against no ring. Prefer A with the steel bearing if it passes RSSI, else B
  (the printed bushing, metal-free). No plastic bearing is used (ruling R14).
- Magnet count: electrical cycles equal to half the magnet count; prefer the count with the
  smaller cogging and a Z to Y amplitude ratio nearer 1.
- Gap: the smallest gap whose peak field stays under 120 mT (TMAG5273A2, 133 mT range) and over
  15 mT. The product gap is 2.7 mm (the 2 mm spacer): the board front sits 1.0 mm behind the
  carrier's rear face, where the magnets are flush. Expected at 2.7 mm with D3 x 1 mm magnets:
  about 39 mT axial peak with 24 magnets. The polarity bumps on the test carriers stand 0.3 mm
  behind the rear face; the product magnet carrier is built with `bumps=False`, which keeps the
  full 1.0 mm to the board.
- If no variant passes, the EC11 encoder fallback is used through J202 (spec 7.2); the decision
  is recorded below.

## Decision record

| Item | Result | Value written to owl_params.py |
|---|---|---|
| Ring mechanism | | |
| Magnet count | | MAGNET_COUNTS |
| Hall gap (mm) | | HALL_GAP_NOMINAL |
| Peak field at that gap (mT) | | |
| TMAG5273 variant and range | | design.toml U302 |
| RSSI no ring / A steel / B (dBm) | | |
| Bearing seat diameter | | BRG_SEAT_D |
| Ring A bore | | RING_A_BORE_D |
| Magnet pocket | | MAG_POCKET_D |
| Encoder fallback needed | | |
