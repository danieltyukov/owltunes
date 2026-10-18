/* Waveshare ESP32-S3-Touch-AMOLED-1.75 (ESP32-S3R8, 16 MB flash, 8 MB octal PSRAM): a 466 x 466
 * round AMOLED with a CO5300 over QSPI and a CST9217 touch controller, the owl's development kit.
 *
 * Sources, all fetched on 18 October 2026:
 *   https://github.com/waveshareteam/ESP32-S3-Touch-AMOLED-1.75 (commit e4344e7): HARDWARE_REFERENCE.md
 *     for the pins and I2C addresses, and Waveshare's ESP-IDF BSP (waveshare/esp32_s3_touch_amoled_1_75
 *     3.0.1, in firmware/brookesia/components/) for the init table, the 6-column gap, the touch
 *     mirrors and the 2-pixel rounder.
 *   https://github.com/waveshareteam/Waveshare-ESP32-components (commit 23a6012):
 *     display/touch/esp_lcd_touch_cst9217 for the touch reset and the point read.
 *   https://github.com/espressif/esp-iot-solution (commit 4962410): components/display/lcd/esp_lcd_co5300,
 *     the panel driver Waveshare's BSP uses, for the panel reset timing.
 *
 * Power: Waveshare's BSP and its demos bring up the display and touch without any AXP2101 or TCA9554
 * transaction (the panel runs on the AXP2101's power-on rails), so this does neither. The PWR button,
 * battery, audio, IMU, RTC and SD card are not driven. The kit has no status LED.
 *
 * Not yet run on the kit. The touch mirrors (both on) are the BSP's defaults and live in this
 * board's sdkconfig.board, so they can be changed like rev A's. */
#include "bsp.h"

#include <stdint.h>

#include "driver/gpio.h"
#include "driver/i2c_types.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "owl_amoled.h"
#include "owl_ui.h"

_Static_assert(OWL_UI_RES == OWL_CO5300_RES, "the UI is laid out for the 466 x 466 panel");

/* HARDWARE_REFERENCE.md, "ESP32-S3 GPIO assignment" and "Shared I2C bus". */
#define PIN_LCD_CS 12
#define PIN_LCD_CLK 38
#define PIN_LCD_D0 4
#define PIN_LCD_D1 5
#define PIN_LCD_D2 6
#define PIN_LCD_D3 7
#define PIN_LCD_RST 39
#define PIN_TP_RST 40
#define PIN_TP_INT 11
#define PIN_I2C_SCL 14
#define PIN_I2C_SDA 15
#define I2C_ADDR_CST9217 0x5A
/* GPIO13 is the panel's TE output; not used yet. */

#define LCD_QSPI_HZ 40000000 /* CO5300_PANEL_IO_QSPI_CONFIG in esp_lcd_co5300 */
#define I2C_HZ 400000        /* the BSP's CONFIG_BSP_I2C_CLK_SPEED_HZ */

static void wait_ms(uint32_t ms)
{
    vTaskDelay(pdMS_TO_TICKS(ms) + 1); /* at least ms: vTaskDelay(n) can return up to a tick early */
}

static void output(int pin, int level)
{
    ESP_ERROR_CHECK(gpio_set_level(pin, level));
    const gpio_config_t config = {
        .pin_bit_mask = 1ULL << pin,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&config));
}

lv_display_t *bsp_display_init(void)
{
    /* Panel reset as esp_lcd_co5300 does it: low for 10 ms, then 150 ms before the first command. */
    output(PIN_LCD_RST, 0);
    wait_ms(10);
    ESP_ERROR_CHECK(gpio_set_level(PIN_LCD_RST, 1));
    wait_ms(150);

    const owl_amoled_panel_t panel = {
        .pin_cs = PIN_LCD_CS,
        .pin_clk = PIN_LCD_CLK,
        .pin_d0 = PIN_LCD_D0,
        .pin_d1 = PIN_LCD_D1,
        .pin_d2 = PIN_LCD_D2,
        .pin_d3 = PIN_LCD_D3,
        .pclk_hz = LCD_QSPI_HZ,
        .init = owl_co5300_init_waveshare_175,
        .init_len = owl_co5300_init_waveshare_175_len,
        .col_offset = OWL_CO5300_WAVESHARE_175_COL_OFFSET,
    };
    lv_display_t *disp = owl_amoled_display_create(&panel);

    /* Touch reset as esp_lcd_touch_cst9217 does it: low for 10 ms, then 50 ms before the first read. */
    output(PIN_TP_RST, 0);
    wait_ms(10);
    ESP_ERROR_CHECK(gpio_set_level(PIN_TP_RST, 1));
    int64_t released = esp_timer_get_time();

    /* GPIO14 and GPIO15 are the board's shared I2C bus (also the AXP2101 at 0x34, the TCA9554 at
     * 0x20 and the sensors); code that drives those later must reuse this bus on I2C0. */
    const owl_amoled_touch_t touch = {
        .chip = OWL_TOUCH_CST9217,
        .i2c_port = I2C_NUM_0,
        .pin_sda = PIN_I2C_SDA,
        .pin_scl = PIN_I2C_SCL,
        .pin_int = PIN_TP_INT,
        .int_pullup = true, /* as Waveshare's CST9217 example (INPUT_PULLUP) */
        .addr = I2C_ADDR_CST9217,
        .scl_hz = I2C_HZ,
        .ready_at_us = released + 50 * 1000LL,
    };
    owl_amoled_touch_create(disp, &touch);
    return disp;
}

void bsp_status_led(uint8_t r, uint8_t g, uint8_t b)
{
    /* The kit has no status LED. */
    (void)r;
    (void)g;
    (void)b;
}
