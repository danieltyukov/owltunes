# OwlTunes enclosure

build123d sources for the ring test prints, enclosure v1, the perch and owl v0 (the owl on the
Waveshare ESP32-S3-Touch-AMOLED-1.75 kit, docs/hardware/kit-owl.md). All dimensions live in
`owl_params.py`; every other module reads them from there.

| Command | What it does |
|---|---|
| `uv run --project enclosure python -m pytest enclosure -q` | Builds every part and checks fits, interference and wall thickness |
| `uv run --project enclosure python enclosure/ring_test.py` | Exports the ring test prints to `build/enclosure/ring-test/` |
| `uv run --project enclosure python enclosure/ring_analysis.py LOG --magnets 24` | Analyses a TMAG5273 log from the ring test |
| `uv run --project enclosure python enclosure/pcb_contract.py` | Writes the board outline and fixed part positions to `hardware/owl-mainboard/mech/contract.json` |
| `uv run --project enclosure python enclosure/owl_v1.py` | Exports enclosure v1 to `build/enclosure/v1/` |
| `uv run --project enclosure python enclosure/perch_v1.py` | Exports the perch v1 body to `build/enclosure/perch-v1/` |
| `uv run --project enclosure python enclosure/owl_kit.py` | Exports owl v0, the owl on the Waveshare AMOLED kit, to `build/enclosure/kit/` |

The owner mark debossed into the back cover and the perch is set in Inter Bold from the
`fonts-inter` package (`sudo apt install fonts-inter`); those two parts do not build without it.

Exports go to `build/`, which is not tracked. Licence: CERN-OHL-P-2.0 (`LICENSE-HARDWARE`), except
`ring_analysis.py`, which is software under MIT (`LICENSE`).

## Owner review points (enclosure v1)

- Glass retention is tape only for rev A (the owner's choice, 17 October 2026). VIEWE supplies only
  the 52.6 mm cover glass (reply of 14 October 2026: the 48.16 mm glass is discontinued), which is
  wider than the bearing's bore, so it rests in front of the bearing on a ring of 0.2 mm
  double-sided tape on the bezel's front face, and only the turning ring surrounds its edge. Nothing
  else holds it: a back-first drop can pull the glass and panel off the tape. A stationary retainer
  round the glass would cost 0.2 mm of depth and most of the display adapter's worst-case slack. For
  v2: a mechanical lock.
- The bearing (or bushing sleeve) has no lip in front of it: it is set flush with the bezel's front
  face on a flat plate at assembly and held by two-part epoxy on its seat.
- The glass's own printed border (outside the 44.16 mm viewing area) is now the visible frame,
  with a 0.5 mm gap to the ring lip over the inner race: confirm on a real panel that the border is
  opaque out to the glass edge.
- The magnet carrier's rear face sits 1.0 mm in front of the board, so a 1.0 mm slot shows under
  the ring band at the side openings. If it is unwanted, the flange's outer part (r 30 to 33) can
  reach back to 0.3 mm from the board without touching the Hall gap.
- Screws are ISO 7380 M2 button heads (black): M2 x 6 from the front through the bezel lugs, M2 x 14
  from the back. The back heads sit 0.2 mm below the cover's back face.

## Owner review points (owl v0)

- The ring turns on the hub's tube, nylon on nylon with 0.25 mm radial and 0.2 mm axial clearance,
  between the glued bezel and the hub's front face. No bearing and no detents: if it feels loose,
  silicone grease on the tube; if it binds, a light sanding of the tube.
- The kit's position comes from Waveshare's drawing and photos (owl_params `KIT_*`). Check the glass
  diameter, the standoff depth and the USB-C position on the real kit before any glue goes on.
- The ear tufts are flexures cut into the head's top wall: a press moves the tip 0.4 mm onto the
  switch. If a switch fires too early or too late, shim it or sand its seat.
