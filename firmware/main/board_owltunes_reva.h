#pragma once

/* OwlTunes main board rev A: ESP32-S3-WROOM-1-N16R8 pin map, bus addresses and board rules.
 *
 * Header only: nothing in the firmware build includes it yet. The rev A board support package
 * arrives with the P3 board selection and takes its pins from here. tools/hw/hw_pinmap.py checks
 * every OWL_PIN_ value against the KiCad netlist of hardware/owl-mainboard (macro OWL_PIN_<NET>
 * must sit on the module pin of net <NET>), and firmware/test_host/test_board_reva.c checks the
 * ESP32-S3 rules: strapping pins, RTC wake pins, ADC1, the pins taken by the octal PSRAM. */

/* Display: CO5300 QSPI on the FSPI IO_MUX pins, so the bus can run at 80 MHz. */
#define OWL_PIN_LCD_CS 10
#define OWL_PIN_LCD_CLK 12
#define OWL_PIN_LCD_D0 11
#define OWL_PIN_LCD_D1 13
#define OWL_PIN_LCD_D2 14
#define OWL_PIN_LCD_D3 9
#define OWL_PIN_LCD_TE 38
#define OWL_PIN_LCD_RST 39 /* active low */
/* TPS22917 ON: high powers the panel and the touch controller (DISP_3V3). 100k pull-down;
 * GPIO46 is a strapping pin and must be low at reset. */
#define OWL_PIN_DISP_EN 46

/* Touch: CST9217 on its own I2C bus (I2C1) with 4.7k pull-ups to DISP_3V3. */
#define OWL_PIN_TP_SDA 47
#define OWL_PIN_TP_SCL 48
#define OWL_PIN_TP_INT 21 /* 10k pull-up to DISP_3V3 */
#define OWL_PIN_TP_RST 40 /* active low */
#define OWL_I2C_ADDR_CST9217 0x5A

/* Always-on sensor bus (I2C0) with 4.7k pull-ups to +3V3. Measure the rise time at 400 kHz at
 * bring-up; if it is too slow, run at 100 kHz or fit 2.2k pull-ups (not lower). */
#define OWL_PIN_I2C_SDA 42
#define OWL_PIN_I2C_SCL 41
#define OWL_I2C_ADDR_TMAG5273 0x35 /* A2 variant; a B2 fitted instead answers at 0x22 */
#define OWL_I2C_ADDR_MAX17048 0x36
#define OWL_I2C_ADDR_LIS2DW12 0x19 /* SA0 pulled high (R309 10k) */
#define OWL_I2C_ADDR_OPT3001 0x44  /* ADDR tied to GND */
#define OWL_I2C_ADDR_DRV2605L 0x5A /* EN tied high: use the STANDBY bit, never let VDD drop */

/* Wake inputs: active low, all RTC GPIOs, for ext1 ANY_LOW deep-sleep wake. Every one has an
 * external pull-up except IMU_INT1, which the LIS2DW12 drives push-pull. The buttons have 100k
 * pull-ups and 10 nF to GND. */
#define OWL_PIN_DOCK_DET 1 /* ADC1_CH0 */
#define OWL_PIN_BTN_EAR_L 2
#define OWL_PIN_BTN_EAR_R 3 /* strapping pin, ignored unless the STRAP_JTAG_SEL eFuse is burned */
#define OWL_PIN_BTN_BEAK 4
#define OWL_PIN_HALL_INT 5  /* TMAG5273 INT, open drain, 47k pull-up; use latched interrupt mode */
#define OWL_PIN_IMU_INT1 6  /* LIS2DW12 INT1: set push-pull, active low (H_LACTIVE = 1) before sleep */
#define OWL_PIN_CHG_PGOOD 7 /* BQ24073 PGOOD, low while input power is valid */
#define OWL_PIN_CHG_STAT 8  /* BQ24073 CHG, low while charging or in a TS fault (not a wake source) */

/* Charger input control: high suspends the input (BQ24073 EN1 with EN2 high); low leaves the
 * input limit set by ILIM (about 0.42 A). 100k pull-down; GPIO45 is the VDD_SPI strapping pin
 * and must be low at reset. */
#define OWL_PIN_CHG_SUSPEND 45

/* Expansion connector J202 (GND, 3V3, A, B; Qwiic pin order): EC11 encoder or I2C. 10k pull-ups.
 * An encoder must rest open at its detents: a closed channel draws 0.33 mA in deep sleep. */
#define OWL_PIN_EXP_A 17
#define OWL_PIN_EXP_B 18

/* Fixed functions. */
#define OWL_PIN_BOOT 0 /* 10k pull-up, pads TP202 and TP203 */
#define OWL_PIN_XTAL32_P 15
#define OWL_PIN_XTAL32_N 16
#define OWL_PIN_USB_DM 19
#define OWL_PIN_USB_DP 20
#define OWL_PIN_U0TXD 43 /* pad TP204; the 499 ohm series resistor is inside the module */
#define OWL_PIN_U0RXD 44 /* pad TP205 */

#define OWL_WAKE_PINS_MASK                                                                                   \
    ((1ULL << OWL_PIN_DOCK_DET) | (1ULL << OWL_PIN_BTN_EAR_L) | (1ULL << OWL_PIN_BTN_EAR_R) |                \
     (1ULL << OWL_PIN_BTN_BEAK) | (1ULL << OWL_PIN_HALL_INT) | (1ULL << OWL_PIN_IMU_INT1) |                  \
     (1ULL << OWL_PIN_CHG_PGOOD))

/* Dock detection on DOCK_DET: 100k pull-up to 3.3 V, 1k series to the pad, perch ID 10k to GND.
 * Docked reads 3300 * (1 + 10) / (100 + 1 + 10) = 327 mV. Treat the owl as docked only when the
 * reading is inside the perch window and CHG_PGOOD is low; a lower reading is a shorted pad. */
#define OWL_DOCK_PULLUP_OHM 100000
#define OWL_DOCK_SERIES_OHM 1000
#define OWL_PERCH_ID_OHM 10000
#define OWL_DOCK_MV_SHORT_MAX 150
#define OWL_DOCK_MV_PERCH_MAX 600
#define OWL_DOCK_MV_OPEN_MIN 2500

/* USB: the charger input limit (R102 3.6k) is 0.42 A typical and 0.48 A worst case, inside USB 2.0
 * default power, so any USB configuration descriptor the firmware sends declares 500 mA. */
#define OWL_USB_MAX_POWER_MA 500

/* Panel power order. Nothing may hold DISP_3V3 up through an I/O pin while it is off.
 * Power-down: 1 display off and sleep-in, wait 120 ms; 2 drive LCD_RST and TP_RST low; 3 hold
 * LCD_CS, LCD_CLK and LCD_D0 to D3 low or high impedance, and turn off the internal pull-ups on
 * TP_SDA, TP_SCL, TP_INT and LCD_TE; 4 DISP_EN low. Keep these levels through deep sleep with the
 * pad hold, because GPIO38 to 40, 47 and 48 are not RTC pads.
 * Power-up: DISP_EN high, wait 10 ms (DISP_3V3 ramps in about 2 ms), then release the resets.
 *
 * Before arming ext1: set IMU_INT1 push-pull and active low (again after any LIS2DW12 reset),
 * and keep the TMAG5273 interrupt in latched mode so a short pulse is not missed. */
