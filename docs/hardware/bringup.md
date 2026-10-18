# Bring-up (rev A)

Do these in order on the first board; stop at the first failure. Pin numbers and levels are in
[pinmap.md](pinmap.md); expected values come from [rev-a.md](rev-a.md).

The rev A firmware (`tools/firmware.sh build owltunes_reva`) drives the display and touch only, so
the other steps that drive pins need a test build that takes its pins from
`firmware/boards/bsp_owltunes_reva/board_owltunes_reva.h`, or the `esptool` and I2C commands of your
choice.

1. **Look.** Under a loupe: U101, U103, U201 and J301 soldered without bridges; D101,
   D102, D201 and D301 cathode bands match the silkscreen; J101 pin 1 marked `+`; RT101 (the 0402
   NTC under the cell area) flat on both pads.
2. **Rails without the battery.** Bench supply on TP103 (VBAT) and TP106 (GND): 3.7 V, 150 mA
   limit. Expect VSYS (TP102) about 3.65 V, +3V3 (TP104) 3.21 to 3.39 V (3.30 V nominal), ESP_EN
   (TP201) high about 10 ms after +3V3, DISP_3V3 (TP105) 0 V, and a supply current under 60 mA
   while the ESP32-S3 boots.
3. **USB.** Plug USB-C into a computer: `lsusb` shows `303a:1001` (USB Serial/JTAG). VIN_CHG
   (TP101) about 4.6 V and CHG_PGOOD low (measure at GPIO7 or R105). With a USB current meter in
   line, the input current settles at or below 0.48 A.
4. **Flash.** Flash over USB with `esptool`. If the module does not enumerate, hold BOOT low
   (short TP202 to TP203) while touching RESET (TP201 to TP203), then release BOOT.
5. **Sensor bus.** An I2C scan on GPIO42 (SDA) and GPIO41 (SCL) finds 0x19, 0x35, 0x36, 0x44 and
   0x5A. Look at SCL and SDA with an oscilloscope at 400 kHz: if the rise time is too slow with
   the 4.7k pull-ups, run at 100 kHz or fit 2.2k (not lower).
6. **Display.** With the panel plugged in and the board unpowered, check DISP_3V3 (TP105) to GND for
   a short with the meter in resistance mode. Then power up and set DISP_EN (GPIO46) high: DISP_3V3
   reaches 3.3 V within 5 ms (about 1.9 ms ramp). Release LCD_RST and initialise the CO5300 over
   QSPI at 40 MHz (the panel allows 50 MHz for writes; do not go to 80). SDA and SCL swing 0 to
   3.3 V at J301 and at R301 and R302 (the touch lines run straight to the panel at 3.3 V, VIEWE's
   reply of 16 October 2026). A touch bus scan on GPIO47 (SDA) and GPIO48 (SCL) finds 0x15 at
   least 100 ms after releasing TP_RST. If it does not, check in this order: TP_RST is high at
   J301 pin 29 after the release; SDA and SCL idle at 3.3 V at J301 and the scope shows an ACK;
   the 100 ms wait after TP_RST is kept. Then run the power-down order from
   `board_owltunes_reva.h` and check that DISP_3V3 falls to near 0 V and stays there: anything above
   about 0.1 V means an I/O pin is feeding the panel.
7. **Haptics.** DRV2605L auto-calibration for the LRA: rated voltage 1.8 V rms, 235 Hz,
   resonant (LRA) mode.
8. **Ring.** Read the TMAG5273 at 0x35 while turning the ring: the angle advances half the
   magnet count of cycles per turn.
9. **Battery and charging.** Check the pack's polarity first (J101 has no reverse-polarity
   protection; see [assembly.md](assembly.md) step 6). Connect the pack with USB plugged in:
   BAT_NTC (U101 pin 1, TS, or RT101's pad on the copper patch side) reads about 0.75 V at 25 C
   (75 uA into RT101's 10k), CHG_STAT (GPIO8) is low while charging, the MAX17048 reports a
   sensible state of charge, and the charge current measured in the battery lead is about 0.27 A
   (0.24 to 0.30 A, set by R101 3.3k; less if the system load takes the input past its 0.37 to
   0.48 A limit). CHG_STAT low with no charge current means a TS fault: RT101 open (a lifted or
   tombstoned pad), or the board at RT101 outside +3.5 to 47.2 C (TS outside 0.30 to 2.1 V). Then
   charge a cell from about 3.5 V with a thermocouple taped to it and compare it with RT101's
   temperature after 30 minutes (R = V(TS) / 75 uA; T in kelvin is
   `1 / (1 / 298.15 + ln(R / 10k) / 3950)`). RT101 reads the board under the cell, so expect it a
   few degrees warmer (see `rev-a.md`, open items).
10. **Perch.** Dock on a powered perch and read DOCK_DET (GPIO1) at once: about 0.33 V (330 mV)
    is right, with CHG_PGOOD low and the LED on the perch lit. 3 V or more means undock at once:
    either the pins do not touch the pads, or the dock-pad board is turned or its cable reversed,
    which puts the perch's 5 V on GPIO1 and can lift +3V3 towards 4 V in deep sleep. Redo the
    meter check of [assembly.md](assembly.md) step 7 before docking again.
11. **Power.** Measure deep-sleep current from the pack (target about 44 uA, see `rev-a.md`),
    screen-on current, and Wi-Fi RSSI against the Waveshare kit at the same spot. If an encoder is
    fitted on J202, check that it rests open at its detents (a closed channel adds 0.33 mA).
12. **RTC.** Compare the 32.768 kHz clock with the main crystal over 10 minutes; drift above
    20 ppm means changing C204 and C205.

## Display and touch at first light

The same checks apply to the Waveshare ESP32-S3-Touch-AMOLED-1.75 kit (`waveshare_amoled_175`),
which has the same CO5300 panel and a CST9217 touch controller. None of this has run on hardware
yet, so expect to adjust it.

1. Build and flash: `tools/firmware.sh flash owltunes_reva`, then open
   `tools/firmware.sh monitor owltunes_reva` and reset the board with Ctrl+T Ctrl+R in the monitor
   (or TP201 to TP203 on rev A): the monitor starts without a reset, so the boot lines are already
   gone otherwise. The log shows `CO5300 up: 11 init commands, column offset 6` (14 on the kit) and
   the screen shows the setup page (compare with `sim/golden/setup_welcome.png`).
2. **Column offset.** The panel's frame starts at RAM column 6 (VIEWE's init sets columns 6 to
   471), and every window the driver sets adds 6. If the picture sits a few pixels to one side with
   a stripe of noise at the left or right edge, the offset is wrong:
   `OWL_CO5300_VIEWE_COL_OFFSET` in `firmware/components/owl_amoled/include/owl_co5300.h` and the
   CASET line of the init table in `owl_co5300.c` must change together (the host test checks that
   they agree).
3. **Colours.** The title and the QR code's background are a warm cream. If they look cold and
   bluish white, red and blue are exchanged: turn on `OWL_LCD_BGR`. If every colour is wrong and
   text edges look speckled, the RGB565 byte order is wrong (the driver sends each pixel high byte
   first, `flush` in `owl_amoled.c`).
4. **Alignment.** The driver widens every redrawn area to start on an even column and row and end
   on an odd one, as the CO5300 needs. Thin lines or text that break up at the edges of redrawn
   areas mean the panel wants something else.
5. **Touch.** Tap near the top, bottom, left and right edges of the screen. If a tap lands on the
   opposite side, turn on `OWL_TOUCH_MIRROR_X` or `OWL_TOUCH_MIRROR_Y`; if moving along one axis
   moves the point along the other, turn on `OWL_TOUCH_SWAP_XY` (the mirrors act on the
   controller's axes, before the swap). All three are off on rev A; the Waveshare kit has both
   mirrors on, as in Waveshare's BSP. To see the controller's raw coordinates next to the mapped
   ones (`touch raw x,y -> x,y`), build with `CONFIG_LOG_DEFAULT_LEVEL_DEBUG=y` added to the
   board's `sdkconfig.board` (every component logs more then; take it out again after). If touch
   does nothing, look for `touch read failed` in the log, then check that TP_INT falls when you
   touch and that 0x15 acknowledges on GPIO47 and 48 (on the kit: GPIO11, and 0x5A on GPIO15 and
   14).

Set these options in the board's `sdkconfig.board` (`firmware/boards/bsp_<board>/`):
`tools/firmware.sh` makes the build's sdkconfig again whenever that file changes.
