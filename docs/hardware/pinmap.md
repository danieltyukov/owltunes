# ESP32-S3 pin map (rev A)

The source of truth is `firmware/main/board_owltunes_reva.h`; `tools/hw/hw_pinmap.py` checks it
against the main board schematic (every `OWL_PIN_<NET>` macro must sit on the module pin of net
`<NET>`, and every connected module GPIO must have a macro), and CI runs that check. The header is
not used by the firmware build yet: rev A board support arrives with the P3 board selection.

Module: ESP32-S3-WROOM-1-N16R8 (U201, KiCad symbol `RF_Module:ESP32-S3-WROOM-1`). Directions are
seen from the ESP32-S3. "Wake source" marks the seven ext1 `ANY_LOW` deep-sleep wake inputs
(`OWL_WAKE_PINS_MASK`), all RTC GPIOs.

| GPIO | Module pin | Net | Direction and level | Notes |
|---|---|---|---|---|
| 0 | 27 | `BOOT` | In (strap) | High at reset for SPI boot; 10k pull-up. Short TP202 to TP203 at reset for download mode |
| 1 | 39 | `DOCK_DET` | Analog in, low when docked | ADC1_CH0. 100k pull-up, 1k to the dock pad; 327 mV on the perch. Wake source |
| 2 | 38 | `BTN_EAR_L` | In, active low | 100k pull-up, 10 nF. Wake source |
| 3 | 15 | `BTN_EAR_R` | In, active low | 100k pull-up, 10 nF. Wake source. Strapping pin (JTAG select), ignored unless the STRAP_JTAG_SEL eFuse is burned |
| 4 | 4 | `BTN_BEAK` | In, active low | 100k pull-up, 10 nF. Wake source |
| 5 | 5 | `HALL_INT` | In, active low | TMAG5273 INT, open drain, 47k pull-up; use latched mode. Wake source |
| 6 | 6 | `IMU_INT1` | In, active low | LIS2DW12 INT1, push-pull, no pull-up; firmware sets it active low (H_LACTIVE = 1). Wake source |
| 7 | 7 | `CHG_PGOOD` | In, active low | BQ24073 PGOOD, low while input power is valid; 100k pull-up. Wake source |
| 8 | 12 | `CHG_STAT` | In, active low | BQ24073 CHG, low while charging; 100k pull-up |
| 9 | 17 | `LCD_D3` | QSPI data | FSPI IO_MUX (FSPIHD) |
| 10 | 18 | `LCD_CS` | Out, active low | FSPI IO_MUX (FSPICS0) |
| 11 | 19 | `LCD_D0` | QSPI data | FSPI IO_MUX (FSPID) |
| 12 | 20 | `LCD_CLK` | Out | FSPI IO_MUX (FSPICLK), up to 80 MHz |
| 13 | 21 | `LCD_D1` | QSPI data | FSPI IO_MUX (FSPIQ) |
| 14 | 22 | `LCD_D2` | QSPI data | FSPI IO_MUX (FSPIWP) |
| 15 | 8 | `XTAL32_P` | Crystal | 32.768 kHz crystal Y201, 18 pF to GND |
| 16 | 9 | `XTAL32_N` | Crystal | 32.768 kHz crystal Y201, 18 pF to GND |
| 17 | 10 | `EXP_A` | In or I2C | J202 pin 3, 10k pull-up. Encoder A or SDA |
| 18 | 11 | `EXP_B` | In or I2C | J202 pin 4, 10k pull-up. Encoder B or SCL |
| 19 | 13 | `USB_DM` | USB | USB Serial/JTAG D-, 22 ohm series, USBLC6 at the receptacle |
| 20 | 14 | `USB_DP` | USB | USB Serial/JTAG D+, 22 ohm series, USBLC6 at the receptacle |
| 21 | 23 | `TP_INT` | In, active low | CST9217 interrupt, 10k pull-up to DISP_3V3; keep the internal pull-up off |
| 35 | 28 | not connected | | Octal PSRAM (N16R8) |
| 36 | 29 | not connected | | Octal PSRAM (N16R8) |
| 37 | 30 | not connected | | Octal PSRAM (N16R8) |
| 38 | 31 | `LCD_TE` | In | CO5300 tearing effect; keep the internal pull-up off |
| 39 | 32 | `LCD_RST` | Out, active low | CO5300 reset; low before DISP_EN goes low |
| 40 | 33 | `TP_RST` | Out, active low | CST9217 reset; low before DISP_EN goes low |
| 41 | 34 | `I2C_SCL` | Open drain | Sensor bus I2C0, 4.7k pull-up to +3V3 |
| 42 | 35 | `I2C_SDA` | Open drain | Sensor bus I2C0, 4.7k pull-up to +3V3 |
| 43 | 37 | `U0TXD` | Out | UART0 TX, pad TP204 (the 499 ohm series resistor is inside the module) |
| 44 | 36 | `U0RXD` | In | UART0 RX, pad TP205 |
| 45 | 26 | `CHG_SUSPEND` | Out, active high | High suspends the charger input (BQ24073 EN1); 100k pull-down. Strapping pin (VDD_SPI), low at reset |
| 46 | 16 | `DISP_EN` | Out, active high | TPS22917 ON, high powers DISP_3V3; 100k pull-down. Strapping pin, low at reset |
| 47 | 24 | `TP_SDA` | Open drain | Touch bus I2C1, 4.7k pull-up to DISP_3V3; keep the internal pull-up off |
| 48 | 25 | `TP_SCL` | Open drain | Touch bus I2C1, 4.7k pull-up to DISP_3V3; keep the internal pull-up off |

Module pin 3 is `ESP_EN` (reset, pad TP201), pin 2 is +3V3 and pins 1, 40 and 41 are GND.

## I2C addresses

| Bus | Device | Address | Set by |
|---|---|---|---|
| Sensor (I2C0, GPIO42 SDA, GPIO41 SCL) | TMAG5273A2 (U302) | 0x35 | A2 variant; a TMAG5273B2 answers at 0x22 |
| Sensor | MAX17048 (U102) | 0x36 | Fixed |
| Sensor | LIS2DW12 (U303) | 0x19 | SA0 pulled high by R309 10k |
| Sensor | OPT3001 (U304) | 0x44 | ADDR tied to GND |
| Sensor | DRV2605L (U301) | 0x5A | Fixed; EN tied high, use the STANDBY bit |
| Touch (I2C1, GPIO47 SDA, GPIO48 SCL) | CST9217 (on the panel) | 0x5A | Fixed; shares 0x5A with the DRV2605L, hence its own bus |

## Panel power order

Nothing may hold `DISP_3V3` up through an I/O pin while it is off. To power the panel down:
display off and sleep-in, wait 120 ms; drive `LCD_RST` and `TP_RST` low; hold `LCD_CS`,
`LCD_CLK` and `LCD_D0` to `LCD_D3` low or high impedance and turn off the internal pull-ups on
`TP_SDA`, `TP_SCL`, `TP_INT` and `LCD_TE`; then `DISP_EN` low. Keep these levels through deep
sleep with the pad hold, because GPIO38 to 40, 47 and 48 are not RTC pads. To power it up:
`DISP_EN` high, wait 10 ms, then release the resets.
