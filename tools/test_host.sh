#!/usr/bin/env bash
# Configure, build and run the host unit tests (with AddressSanitizer and UBSan).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${ROOT}/build/test_host"
cmake -S "${ROOT}/firmware/test_host" -B "${BUILD}" -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build "${BUILD}"
ctest --test-dir "${BUILD}" --output-on-failure
