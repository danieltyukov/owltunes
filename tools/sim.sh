#!/usr/bin/env bash
# Build the simulator and compare every screen with its golden image.
#   tools/sim.sh            run the comparisons
#   tools/sim.sh --update   regenerate sim/golden/*.png (look at every image before committing)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${ROOT}/build/sim"
cmake -S "${ROOT}/sim" -B "${BUILD}" -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build "${BUILD}"
if [[ "${1:-}" == "--update" ]]; then
    mkdir -p "${ROOT}/sim/golden"
    for scenario in $("${BUILD}/owl_sim" list); do
        "${BUILD}/owl_sim" update-golden "${scenario}" "${ROOT}/sim/golden"
        echo "updated sim/golden/${scenario}.png"
    done
    exit 0
fi
ctest --test-dir "${BUILD}" --output-on-failure
