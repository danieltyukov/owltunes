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
| `uv run --project enclosure python enclosure/perch_v1.py` | Exports the perch v1 body to `build/enclosure/perch-v1/` |

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
- Screws are ISO 7380 M2 button heads (black): M2 x 6 from the front through the bezel lugs, M2 x 14
  from the back. The back heads sit 0.2 mm below the cover's back face.
