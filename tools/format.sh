#!/usr/bin/env bash
# Format the C code with the pinned clang-format (no system install needed), or check it.
#   tools/format.sh           rewrite files in place
#   tools/format.sh --check   fail if any file differs from .clang-format (CI runs this)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
VERSION=23.1.2
mapfile -t FILES < <(git ls-files '*.c' '*.h' | grep -v '/fonts/')
if command -v uvx >/dev/null 2>&1; then
    CLANG_FORMAT=(uvx --from "clang-format==${VERSION}" clang-format)
else
    CLANG_FORMAT=(pipx run --spec "clang-format==${VERSION}" clang-format)
fi
if [[ "${1:-}" == "--check" ]]; then
    "${CLANG_FORMAT[@]}" --dry-run --Werror "${FILES[@]}"
    echo "C formatting matches .clang-format"
else
    "${CLANG_FORMAT[@]}" -i "${FILES[@]}"
fi
