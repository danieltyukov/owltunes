#!/usr/bin/env bash
# Product renders from the real enclosure and board files (Blender Cycles).
#   tools/render.sh                  export the meshes, then render every scene into docs/img/
#   tools/render.sh desk pocket      only these scenes
#   SAMPLES=64 SIZE=1200x750 tools/render.sh hero     a quick, smaller preview
# Needs uv (enclosure), kicad-cli (the board) and blender (5.2 or later) on PATH. A full set takes a
# while on a laptop CPU; the scenes are independent, so they can run on separate machines.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/build/render"
SAMPLES="${SAMPLES:-256}"
SIZE="${SIZE:-1920x1080}"
scenes=("$@")
[[ ${#scenes[@]} -gt 0 ]] || scenes=(hero desk pocket exploded)

uv run --project "${ROOT}/enclosure" python "${ROOT}/enclosure/render_export.py"
kicad-cli pcb export glb --force --user-origin 100x100mm --include-silkscreen --include-soldermask \
    --include-pads --no-dnp --subst-models -o "${OUT}/pcb.glb" "${ROOT}/hardware/owl-mainboard/owl-mainboard.kicad_pcb"
for scene in "${scenes[@]}"; do
    blender -b --factory-startup -P "${ROOT}/tools/render/owl_render.py" -- \
        "${scene}" "${ROOT}/docs/img/render-${scene}.jpg" --samples "${SAMPLES}" --size "${SIZE}"
done
