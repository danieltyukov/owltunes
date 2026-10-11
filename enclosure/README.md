# OwlTunes enclosure

build123d sources for the ring test prints, enclosure v1 and the perch. All dimensions live in
`owl_params.py`; every other module reads them from there.

| Command | What it does |
|---|---|
| `uv run --project enclosure python -m pytest enclosure -q` | Builds every part and checks fits, interference and wall thickness |
| `uv run --project enclosure python enclosure/ring_test.py` | Exports the ring test prints to `build/enclosure/ring-test/` |
| `uv run --project enclosure python enclosure/ring_analysis.py LOG --magnets 24` | Analyses a TMAG5273 log from the ring test |
| `uv run --project enclosure python enclosure/pcb_contract.py` | Writes the board outline and fixed part positions to `hardware/owl-mainboard/mech/contract.json` |
| `uv run --project enclosure python enclosure/owl_v1.py` | Exports enclosure v1 to `build/enclosure/v1/` |

Exports go to `build/`, which is not tracked. Licence: CERN-OHL-P-2.0 (`LICENSE-HARDWARE`), except
`ring_analysis.py`, which is software under MIT (`LICENSE`).

## Owner review points (enclosure v1)

- Glass retention is adhesive for rev A: the cover glass goes into the bezel from the front on an
  adhesive ring, and a 1.3 mm retainer ring is glued into the lip opening over the glass border
  (outside the viewing area). The glass cannot come out unless the retainer's glue joint fails too.
  A snap does not fit the 1.3 mm lip with the bearing right behind it. For v2: a mechanical lock
  for the retainer (a taller lip or a bayonet).
- Screws are ISO 7380 M2 button heads (black): M2 x 6 from the front through the bezel lugs, M2 x 14
  from the back. The back heads sit 0.2 mm below the cover's back face.
