# The Arduino Nano ESP32 as a dev board

The Arduino Nano ESP32 carries the same chip and memory as the owl's own board: an ESP32-S3 (in a
u-blox NORA-W106 module) with 16 MB of flash and 8 MB of octal PSRAM. It has no display, so the
firmware draws the owl's screens into memory where nothing shows them. The setup protocol over USB,
the RGB status LED and Wi-Fi work now, and the board runs the Spotify login itself
([Linking Spotify](#linking-spotify)); later P3a tasks add Spotify control.

## Build and flash

With ESP-IDF v6.1 activated and the board on USB:

```bash
tools/firmware.sh build nano_esp32
tools/firmware.sh flash nano_esp32      # finds the board under /dev/serial/by-id/
tools/firmware.sh monitor nano_esp32    # the console, without restarting the board; Ctrl+] quits
```

The build lives in `build/firmware-nano_esp32` with its own `sdkconfig`, made from
`firmware/sdkconfig.defaults` and `firmware/boards/bsp_nano_esp32/sdkconfig.board`. Change those
two files, not the generated `sdkconfig`: the script makes it again whenever they change.

On Linux the board shows up as `/dev/ttyACM0` or `/dev/ttyACM1`, and the number changes when it
resets. The scripts use the stable name under `/dev/serial/by-id/` that contains `Espressif`.
Your user needs to be in the `dialout` group to open it.

## First flash, and recovery

A board that still runs Arduino's firmware, or firmware that crashes at once, may not reset into
the bootloader by itself. Put it into ROM download mode by hand:

1. Connect pin B1 to GND with a wire. B1 is on the A0 to A7 edge, the third hole from the end
   away from the USB socket, next to GND. The green LED lights.
2. Press and release RST. The LED turns purple: the board waits in download mode.
3. Remove the wire and flash from `build/firmware-nano_esp32` with
   `python -m esptool --chip esp32s3 --before no-reset --after watchdog-reset write-flash @flash_args`
   (or `tools/hil_nano.py --rom`). Only a watchdog reset starts the new firmware from this state.

Once the OwlTunes firmware runs, `tools/firmware.sh flash` works without the wire.

To go back to Arduino's firmware, write the full-flash backup you made before the first flash:
`python -m esptool --chip esp32s3 write-flash 0 <backup>.bin`. Keep such backups in `private/`.

## The console

The USB port carries the firmware's log, the setup protocol (`@owl` lines, see
[the protocol](provisioning-protocol.md)) and developer commands such as `info` ([console](console.md)). The setup page connects to the same port over Web
Serial, so close the monitor before you connect the page: only one program can hold the port.

Console output is dropped when nobody is reading the port, so the firmware never stalls waiting
for a host. After the transmit buffer fills, a line may be cut short. If the setup page reports the
port as busy, close the monitor (or any other program holding it) and connect again.

## Status LED

The RGB LED shows the one thing the owl most needs you to know. The console's `info` command
reports the same status by name ([console](console.md)). The Wi-Fi, login and
playback statuses appear as those features arrive: until then only `needs_wifi`, `joining`,
`needs_login`, `linking`, `log_in_again` and `starting` can show (`starting` is what a linked,
online owl shows until playback support arrives), and `backoff`, `rate_limited` or `quota` while a
refresh of the Spotify login waits to be tried again.

| LED | Status | Meaning |
|---|---|---|
| Blue, slow blink | `needs_wifi` | No Wi-Fi network saved: open the setup page |
| Blue, fast blink | `joining` | Joining a saved network, or waiting to try again |
| Amber, slow blink | `needs_login` | Online, but not linked to Spotify yet |
| Cyan, fast blink | `linking` | Exchanging the Spotify login code |
| Red, slow blink | `log_in_again` | Spotify refused the saved login: log in again |
| Green, fast blink | `starting` | Linked and online, reading the playback state |
| Green | `playing` | Something is playing |
| Dim green | `paused` | Playback is paused |
| Amber | `no_device` | No Spotify device is active: start Spotify on a phone or computer |
| Magenta, slow blink | `rate_limited` | Spotify asked the owl to slow down for a moment |
| White, slow blink | `backoff` | The network or Spotify's servers failed: the owl retries after a pause that grows from 2 s to 60 s |
| Magenta | `quota` | Spotify's quota for the app is used up until its Retry-After time |

## Hardware test

`tools/hil_nano.py` flashes the build, resets the board and checks that it runs the firmware just
built, finds its 8 MB of PSRAM, runs from the first OTA slot, keeps at least 32 KB of internal RAM
free and answers on the console. With no network saved it also checks that the owl refuses to
start a Spotify login while it is offline, and without a login that it refuses `next` and `auth`
with `not_linked`. `--fresh` erases the saved settings first, `--no-flash` only
resets the board, and `--rom` flashes a board that waits in ROM download mode. `--wifi` and
`--missing-network` add the Wi-Fi checks described below. The console log of the run is in
`build/hil-nano/console.log`.

Opening the serial port resets the board: the USB-Serial/JTAG controller restarts the chip
when a program opens the port (reset reason `usb` in `info`); opening it reset the board 3 of 3 times
with DTR and RTS held low.
Every open therefore starts the firmware again, and the scripts wait for its `OWL_BOOT_OK` line
before they send anything. A terminal opened while a test runs restarts the board too.

## Wi-Fi

The board joins the saved networks in the order they were saved (home first, then a phone
hotspot) and goes on to the next one when a network fails. When all of them fail it waits 5 s
before trying again, and longer each time up to a minute. It joins 2.4 GHz networks only.

For the hardware test with Wi-Fi, put a 2.4 GHz network in `private/hil.env` (git ignores
`private/`):

```text
OWL_WIFI_SSID=Your network
OWL_WIFI_PASSWORD=its password
```

Then run `tools/hil_nano.py --wifi`. It saves a network that is never in range ahead of yours,
checks that the owl reports it and joins yours next, and checks that the owl rejoins by itself
after a reset. The password goes to the board only; the script never prints it.

`tools/hil_nano.py --missing-network` needs no credentials. It saves only the network that is never
in range, checks that the owl reports `wifi_not_found`, waits 5 s before the next round and 10 s
before the one after, and stops once the network is removed again. Other saved networks would
change what it sees, so it refuses to run while any are saved.

## Linking Spotify

Create your own Spotify app as the [setup guide](setup-guide.md) describes, and add these
redirect URIs to it:

- `http://127.0.0.1:8765/callback` for `tools/owl_login.py`,
- `http://127.0.0.1:4173/owltunes/callback/` for the setup page served from this computer,
- `https://danieltyukov.github.io/owltunes/callback/` for the published setup page.

Put the app's client ID in `private/hil.env` as `OWL_SPOTIFY_CLIENT_ID=...`, then, with a Wi-Fi
network saved on the board, run in your own terminal:

```bash
tools/owl_login.py --open
```

Opening the port restarts the board, so the script waits until the owl has started and joined its
network, and keeps the port open until it is done. It then saves the client ID on the owl, opens
Spotify's login page, receives Spotify's answer on `http://127.0.0.1:8765/callback` and hands the
code to the owl over USB. The owl exchanges it for tokens itself; they never leave the board. The
script then resets the owl and waits until the saved login passes its check with Spotify. The
login address it prints carries your client ID, so keep it to yourself. The console log in
`build/owl-login/console.log` shows the client ID as `<redacted>`, and the script fails if
anything in that log looks like a token. While the owl exchanges the code its LED blinks cyan
quickly; once linked it blinks green quickly (`starting`) until playback support arrives.

The owl starts a login only while it is online; otherwise `spotify_begin` answers `offline`.

To try the setup page against the board without publishing it, run
`cd web && npm run build && npx vite preview --port 4173 --host 127.0.0.1 --base /owltunes/` and
open `http://127.0.0.1:4173/owltunes/setup/`. Use `127.0.0.1`, not `localhost`: Spotify accepts
plain HTTP only for the loopback address.
