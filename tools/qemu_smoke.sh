#!/usr/bin/env bash
# Boot the firmware in QEMU headlessly and wait for the boot marker. Requires ESP-IDF v6.1.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${ROOT}/build/qemu-smoke.log"
mkdir -p "${ROOT}/build"
cd "${ROOT}"
# idf.py is a program on PATH after export.sh (CI) but only a shell function after the EIM
# activation script, which child processes cannot see; fall back to calling it through Python.
if command -v idf.py >/dev/null 2>&1; then
    IDF_PY=(idf.py)
elif [[ -n "${IDF_PATH:-}" && -n "${IDF_PYTHON_ENV_PATH:-}" ]]; then
    IDF_PY=("${IDF_PYTHON_ENV_PATH}/bin/python" "${IDF_PATH}/tools/idf.py")
else
    echo "ESP-IDF v6.1 is not activated (no idf.py, IDF_PATH or IDF_PYTHON_ENV_PATH)" >&2
    exit 2
fi
# The virtual RGB panel needs a graphics backend; SDL's dummy driver provides one without a window.
SDL_VIDEODRIVER=dummy timeout 90 "${IDF_PY[@]}" -C firmware -B build/firmware qemu --graphics >"${LOG}" 2>&1 || true
if grep -q "OWL_BOOT_OK" "${LOG}"; then
    grep "OWL_BOOT_OK\|demo player parsed" "${LOG}"
    echo "QEMU smoke test passed"
    exit 0
fi
echo "QEMU smoke test failed; last lines of ${LOG}:"
tail -40 "${LOG}"
exit 1
