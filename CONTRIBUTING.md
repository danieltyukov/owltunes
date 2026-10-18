# Contributing to OwlTunes

Thanks for helping. This file covers how to build, test and submit changes.

## Before you start

Read the [system design](docs/design/2026-10-04-owltunes-system-design.md). Changes that alter
how the parts fit together should start as an issue so the design can be discussed first.

## Checks that must pass

| Check | Command |
|---|---|
| Writing style | `python3 tools/check_style.py` |
| Host unit tests | `tools/test_host.sh` |
| Simulator screenshots | `tools/sim.sh` |
| Firmware build | `tools/firmware.sh build`, then `build nano_esp32`, `build owltunes_reva` and `build waveshare_amoled_175` (with ESP-IDF v6.1 activated) |
| C formatting | `tools/format.sh --check` (`tools/format.sh` fixes it) |
| Setup protocol in QEMU | `tools/qemu_prov_test.py` (after the firmware build) |
| Hardware smoke test (Arduino Nano ESP32 on USB, optional) | `tools/hil_nano.py` (after `tools/firmware.sh build nano_esp32`) |
| Real-account test (linked board on USB, opt-in, controls your Spotify playback) | `tools/hil_spotify.py --real-account` |
| Setup site | `cd web && npm ci && npm test && npx playwright install chromium && npm run e2e` |

## Writing style

Plain, direct English. The style check rejects em dashes, en dashes and emoji in tracked files.
Write non-ASCII test data as escapes.

## Code style

C11, four-space indent, `.clang-format` in the repository root, braces on every block. Keep each
file focused on one job. New behaviour needs a test.

## Commits

Use conventional commit prefixes (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). One logical
change per commit; describe the change itself.
