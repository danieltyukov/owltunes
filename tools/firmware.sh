#!/usr/bin/env bash
# Build or emulate the firmware. Requires an activated ESP-IDF v6.1.
#   tools/firmware.sh build   build for the ESP32-S3
#   tools/firmware.sh qemu    build, then run in QEMU with the virtual display
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
IDF=("${IDF_PY[@]}" -C firmware -B build/firmware)
case "${1:-build}" in
build)
    "${IDF[@]}" set-target esp32s3
    "${IDF[@]}" build
    ;;
qemu)
    "${IDF[@]}" build
    "${IDF[@]}" qemu --graphics monitor
    ;;
*)
    echo "usage: tools/firmware.sh build|qemu" >&2
    exit 2
    ;;
esac
