# The Arduino Nano ESP32 as a dev board

The Arduino Nano ESP32 carries the same chip and memory as the owl's own board: an ESP32-S3 (in a
u-blox NORA-W106 module) with 16 MB of flash and 8 MB of octal PSRAM. It has no display, so the
firmware draws the owl's screens into memory where nothing shows them. The setup protocol over USB
works now. The board stays offline until later P3a tasks add Wi-Fi, the Spotify login and Spotify
control, and the RGB LED showing the owl's status is planned for a later task too.

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
online owl shows until playback support arrives).

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
| Magenta | `quota` | Spotify's quota for the app is used up until its Retry-After time |

## Hardware test

`tools/hil_nano.py` flashes the build, resets the board and checks that it runs the firmware just
built, finds its 8 MB of PSRAM, runs from the first OTA slot, keeps at least 32 KB of internal RAM
free and answers on the console. `--fresh` erases the saved settings first, `--no-flash` only
resets the board, and `--rom` flashes a board that waits in ROM download mode. The console log of
the run is in `build/hil-nano/console.log`.

Opening the serial port resets the board: the USB-Serial/JTAG controller restarts the chip
when a program opens the port (reset reason `usb` in `info`); opening it reset the board 3 of 3 times
with DTR and RTS held low.
Every open therefore starts the firmware again, and the scripts wait for its `OWL_BOOT_OK` line
before they send anything. A terminal opened while a test runs restarts the board too.
