#!/usr/bin/env bash
# Regenerate the UI fonts in firmware/components/owl_ui/fonts/ from the pinned Inter release.
# Inter covers Latin (with accents), Greek and Cyrillic, so artist and track names render
# correctly. Symbols (Wi-Fi, battery, play) fall back to LVGL's built-in Montserrat fonts.
# Needs curl, unzip, python3 and Node.js (npx).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${ROOT}/build/fonts"
OUT="${ROOT}/firmware/components/owl_ui/fonts"
INTER_URL="https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
INTER_SHA256="9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e"
# Printable ASCII, Latin-1 Supplement, Latin Extended-A, Greek, Cyrillic, common punctuation, euro.
RANGES="0x20-0x7E,0xA0-0x17F,0x370-0x3FF,0x400-0x45F,0x2010-0x2027,0x20AC"

mkdir -p "${WORK}" "${OUT}"
if [[ ! -f "${WORK}/Inter-4.1.zip" ]]; then
    curl -fsSL -o "${WORK}/Inter-4.1.zip" "${INTER_URL}"
fi
echo "${INTER_SHA256}  ${WORK}/Inter-4.1.zip" | sha256sum -c -
unzip -o -q "${WORK}/Inter-4.1.zip" "extras/ttf/Inter-SemiBold.ttf" "extras/ttf/Inter-Medium.ttf" "LICENSE.txt" -d "${WORK}"
cp "${WORK}/LICENSE.txt" "${OUT}/LICENSE-Inter.txt"

gen() { # name size ttf
    npx -y lv_font_conv@1.5.3 --font "${WORK}/extras/ttf/$3" -r "${RANGES}" --size "$2" --bpp 4 --no-compress \
        --format lvgl --lv-include lvgl.h --lv-font-name "$1" --lv-fallback "lv_font_montserrat_$2" \
        -o "${OUT}/$1.c"
}
gen owl_font_28 28 Inter-SemiBold.ttf
gen owl_font_20 20 Inter-Medium.ttf
gen owl_font_14 14 Inter-Medium.ttf

# The generator writes each glyph into a comment and absolute paths into the header; keep the
# sources ASCII for the style check and free of local paths.
python3 - "${OUT}" "${ROOT}" <<'PY'
import pathlib, sys
for f in pathlib.Path(sys.argv[1]).glob("owl_font_*.c"):
    text = f.read_text(encoding="utf-8").replace(sys.argv[2] + "/", "")
    f.write_text("".join(c if ord(c) < 128 else "?" for c in text), encoding="utf-8")
PY
echo "fonts written to ${OUT}"
