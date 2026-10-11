# The Arduino Nano ESP32 as a dev board

The Arduino Nano ESP32 carries the same chip and memory as the owl's own board: an ESP32-S3 (in a
u-blox NORA-W106 module) with 16 MB of flash and 8 MB of octal PSRAM. It has no display, so the
firmware draws the owl's screens into memory where nothing shows them, and the board's RGB LED
shows the owl's status instead. Everything else runs as it will on the owl: the setup protocol
over USB, Wi-Fi, the Spotify login and Spotify control.

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

The USB port carries the firmware's log and the setup protocol (`@owl` lines, see
[the protocol](provisioning-protocol.md)). The setup page connects to the same port over Web
Serial, so close the monitor before you connect the page: only one program can hold the port.
