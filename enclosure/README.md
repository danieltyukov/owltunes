# OwlTunes enclosure

build123d sources for the ring test prints, enclosure v1 and the perch. All dimensions live in
`owl_params.py`; every other module reads them from there.

| Command | What it does |
|---|---|
| `uv run --project enclosure python -m pytest enclosure -q` | Builds every part and checks fits, interference and wall thickness |
| `uv run --project enclosure python enclosure/ring_test.py` | Exports the ring test prints to `build/enclosure/ring-test/` |
| `uv run --project enclosure python enclosure/ring_analysis.py LOG --magnets 24` | Analyses a TMAG5273 log from the ring test |

Exports go to `build/`, which is not tracked. Licence: CERN-OHL-P-2.0 (`LICENSE-HARDWARE`), except
`ring_analysis.py`, which is software under MIT (`LICENSE`).
