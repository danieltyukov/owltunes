#!/usr/bin/env bash
# Build, flash or emulate the firmware. Requires an activated ESP-IDF v6.1.
#   tools/firmware.sh build [board]          build for a board, named after firmware/boards/bsp_<board>
#                                            (qemu when no board is given)
#   tools/firmware.sh qemu                   build for QEMU, then run it with the virtual display
#   tools/firmware.sh flash <board> [port]   build, then flash a real board over USB
#   tools/firmware.sh monitor <board> [port] open the console without restarting the board
#                                            (Ctrl+] quits)
# Each board builds in its own directory (QEMU in build/firmware, where the QEMU tests look; other
# boards in build/firmware-<board>) with its own sdkconfig. That sdkconfig is made again from
# firmware/sdkconfig.defaults and firmware/boards/bsp_<board>/sdkconfig.board whenever one of them
# is newer, so the tracked files stay the only source of the configuration. The port defaults to the
# one USB device under /dev/serial/by-id/ whose name contains Espressif.
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

usage() {
    echo "usage: tools/firmware.sh build [board] | qemu | flash <board> [port] | monitor <board> [port]" >&2
    exit 2
}

ACTION="${1:-build}"
case "${ACTION}" in
build) BOARD="${2:-qemu}" ;;
qemu) BOARD=qemu ;;
flash | monitor) BOARD="${2:-}" ;;
*) usage ;;
esac
if [[ -z "${BOARD}" || ! -f "firmware/boards/bsp_${BOARD}/sdkconfig.board" ]]; then
    echo "unknown board '${BOARD}'; boards: $(cd firmware/boards && ls -d bsp_*/ | sed 's/^bsp_//; s#/##' | tr '\n' ' ')" >&2
    exit 2
fi
if [[ "${BOARD}" == qemu ]]; then
    BUILD="build/firmware"
else
    BUILD="build/firmware-${BOARD}"
fi
SDKCONFIG="${ROOT}/${BUILD}/sdkconfig"
mkdir -p "${BUILD}"
for defaults in firmware/sdkconfig.defaults "firmware/boards/bsp_${BOARD}/sdkconfig.board"; do
    if [[ -f "${SDKCONFIG}" && "${defaults}" -nt "${SDKCONFIG}" ]]; then
        echo "${defaults} changed: making ${BUILD}/sdkconfig again"
        rm -f "${SDKCONFIG}" "${SDKCONFIG}.old"
    fi
done
IDF=("${IDF_PY[@]}" -C firmware -B "${BUILD}" -DOWL_BOARD="${BOARD}" -DSDKCONFIG="${SDKCONFIG}")

port() {
    if [[ -n "${1:-}" ]]; then
        echo "$1"
        return
    fi
    local found=(/dev/serial/by-id/*Espressif*)
    if [[ ! -e "${found[0]}" || ${#found[@]} -ne 1 ]]; then
        echo "connect exactly one board, or name its port (found: ${found[*]})" >&2
        exit 2
    fi
    echo "${found[0]}"
}

case "${ACTION}" in
build)
    "${IDF[@]}" build
    ;;
qemu)
    "${IDF[@]}" build
    "${IDF[@]}" qemu --graphics monitor
    ;;
flash)
    "${IDF[@]}" build
    "${IDF[@]}" -p "$(port "${3:-}")" flash
    ;;
monitor)
    "${IDF[@]}" -p "$(port "${3:-}")" monitor --no-reset
    ;;
esac
