# OwlTunes

OwlTunes is an owl-shaped remote control for Spotify that sits on your desk and fits in your
pocket.

It controls the music that is already playing on your phone, computer or speakers; it plays no
audio itself. Turn the ring around its round screen to change the volume or scroll, tap to pause,
press an ear to skip, and browse your playlists and devices without taking your phone out. Put it
on its perch and it becomes a desk display that charges while it shows what is playing.

**Status:** early development. The design is complete and the firmware, simulator, PCB and
enclosure are being built in the open. Read the
[system design](docs/design/2026-10-04-owltunes-system-design.md) for the full picture.
The firmware runs on an Arduino Nano ESP32 as a headless dev board, and the setup page sets it up
over USB ([dev board guide](docs/dev-board-nano-esp32.md)). Joining Wi-Fi, linking to Spotify and
controlling playback from its USB console are written and tested on the host and in QEMU; their
first run on the board against a real network and Spotify account is still to come. The
round-screen dev kit is next.

## How it works

- **The owl:** ESP32-S3, 1.75 inch round AMOLED touch display, a rotating ring with haptic
  clicks, two ear buttons, a beak button, a battery and USB-C.
- **The perch:** a weighted magnetic desk dock that charges the owl through spring contacts.
- **Spotify:** the owl talks to the Spotify Web API over Wi-Fi (home network or phone hotspot).
  Bluetooth media keys keep play, skip and volume working when there is no internet.

## What it looks like

These are real renders from the simulator, which runs the same UI code as the firmware.

| Now playing | Playlists | Preset wheel | Looking for your phone |
|---|---|---|---|
| ![Now playing](docs/img/now_playing.png) | ![Playlists](docs/img/playlists.png) | ![Preset wheel](docs/img/presets_wheel.png) | ![No device](docs/img/no_device.png) |

The album art is a generated placeholder; the device shows the real cover.

## Repository layout

| Path | Contents |
|---|---|
| `docs/` | Design documents and guides |
| `firmware/` | ESP-IDF firmware; `firmware/components/` holds the shared C code and `firmware/boards/` the support for each board |
| `sim/` | Desktop simulator and golden screenshots |
| `web/` | The setup site (TypeScript and Vite), published on GitHub Pages |
| `enclosure/` | build123d sources for the owl, the ring and the perch |
| `hardware/` | KiCad 10 projects for the owl main board and the perch board |
| `docs/hardware/` | Hardware notes, ring test, assembly, bring-up and ordering |
| `tools/` | Build, test, style and font scripts |

## Building

Linux with CMake 3.22+, Ninja and a C compiler.

| What | Command |
|---|---|
| Unit tests (with sanitizers) | `tools/test_host.sh` |
| Simulator screenshot tests | `tools/sim.sh` |
| Interactive simulator (needs `libsdl2-dev`) | `cmake -S sim -B build/sim-sdl -G Ninja -DOWL_SIM_SDL=ON && cmake --build build/sim-sdl && build/sim-sdl/owl_sim sdl` |
| Firmware (ESP-IDF v6.1 activated) | `tools/firmware.sh build` |
| Firmware for the Arduino Nano ESP32, and flashing it | `tools/firmware.sh build nano_esp32`, then `tools/firmware.sh flash nano_esp32` |
| Hardware tests on the Nano ESP32 (board on USB) | `tools/hil_nano.py --wifi`; with a linked board and your consent, `tools/hil_spotify.py --real-account` |
| Firmware in the QEMU emulator | `tools/qemu_smoke.sh` |
| Setup protocol in QEMU, including a real HTTPS call to Spotify | `tools/qemu_prov_test.py` |
| Setup site: unit and browser tests (Node.js 22) | `cd web && npm ci && npm test && npm run e2e` |
| Setup site: local development server | `cd web && npm run dev` |
| Regenerate the UI fonts (needs Node.js) | `tools/gen_fonts.sh` |

The UI font is [Inter](https://rsms.me/inter/) (SIL Open Font License, see
`firmware/components/owl_ui/fonts/LICENSE-Inter.txt`).

## Setting it up

OwlTunes needs Spotify Premium and your own free Spotify developer app (client ID). It uses the
Authorization Code flow with PKCE, so no client secret is ever stored on the device or in this
repository.

Open the [setup page](https://danieltyukov.github.io/owltunes/setup/) in Chrome or Edge, connect
the owl over USB, add your Wi-Fi networks and your client ID, and log in with Spotify. The
[setup guide](docs/setup-guide.md) walks through every step, including creating the Spotify app,
and the [protocol notes](docs/provisioning-protocol.md) describe what the page and the owl say to
each other.

<img src="docs/img/setup.png" alt="The owl's setup screen with a QR code for the setup page" width="240">

## Licences

- Software: [MIT](LICENSE)
- Hardware and enclosure designs: [CERN-OHL-P-2.0](LICENSE-HARDWARE)

## Not affiliated with Spotify

OwlTunes is an independent, non-commercial project. It is not affiliated with, endorsed by or
sponsored by Spotify. Spotify is a trademark of Spotify AB.
