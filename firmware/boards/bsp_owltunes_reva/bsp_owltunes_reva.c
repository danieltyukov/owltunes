/* OwlTunes main board rev A (ESP32-S3-WROOM-1-N16R8): the VIEWE ALL-UEOL018VG-RA31-A001A round
 * AMOLED (466 x 466, CO5300 over QSPI) and its CST820 touch controller. Pins, bus speeds and the panel
 * power order come from board_owltunes_reva.h, the init sequence from VIEWE.
 *
 * Not yet run on the board. To check at first light (docs/hardware/bringup.md): the 6-column offset
 * (a frame shifted sideways or a stripe of noise at one edge means it is wrong), the colours
 * (OWL_LCD_BGR), and the touch axes (OWL_TOUCH_SWAP_XY, OWL_TOUCH_MIRROR_X, OWL_TOUCH_MIRROR_Y, all off
 * by default because nothing says how the CST820 sits against the panel). The CST820 is read with the
 * CST816S register layout (finger count at 0x02, X and Y at 0x03 to 0x06), also unverified. Rev A has
 * no status LED; the ring, haptics, sensors and charger are not driven yet. */
#include "bsp.h"

#include <stdint.h>

#include "board_owltunes_reva.h"
#include "driver/gpio.h"
#include "driver/i2c_types.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "owl_amoled.h"
#include "owl_ui.h"

_Static_assert(OWL_UI_RES == OWL_CO5300_RES, "the UI is laid out for the 466 x 466 panel");

#define POWER_SETTLE_MS 10   /* DISP_EN high to the resets' release */
#define RESET_TO_FIRST_MS 10 /* reset release to the first panel command */

static void wait_ms(uint32_t ms)
{
    vTaskDelay(pdMS_TO_TICKS(ms) + 1); /* at least ms: vTaskDelay(n) can return up to a tick early */
}

static void output(int pin, int level)
{
    ESP_ERROR_CHECK(gpio_set_level(pin, level)); /* latched before the driver turns on, so no glitch */
    const gpio_config_t config = {
        .pin_bit_mask = 1ULL << pin,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&config));
}

/* The power-up order in board_owltunes_reva.h: DISP_EN high with LCD_RST and TP_RST held low, wait
 * 10 ms (DISP_3V3 ramps in about 2 ms), release both, first panel command 10 ms later. Returns when
 * the resets were released. */
static int64_t power_up(void)
{
    output(OWL_PIN_LCD_RST, 0);
    output(OWL_PIN_TP_RST, 0);
    output(OWL_PIN_DISP_EN, 1);
    wait_ms(POWER_SETTLE_MS);
    ESP_ERROR_CHECK(gpio_set_level(OWL_PIN_LCD_RST, 1));
    ESP_ERROR_CHECK(gpio_set_level(OWL_PIN_TP_RST, 1));
    int64_t released = esp_timer_get_time();
    wait_ms(RESET_TO_FIRST_MS);
    return released;
}

lv_display_t *bsp_display_init(void)
{
    int64_t released = power_up();

    const owl_amoled_panel_t panel = {
        .pin_cs = OWL_PIN_LCD_CS,
        .pin_clk = OWL_PIN_LCD_CLK,
        .pin_d0 = OWL_PIN_LCD_D0,
        .pin_d1 = OWL_PIN_LCD_D1,
        .pin_d2 = OWL_PIN_LCD_D2,
        .pin_d3 = OWL_PIN_LCD_D3,
        .pclk_hz = OWL_LCD_QSPI_HZ,
        .init = owl_co5300_init_viewe,
        .init_len = owl_co5300_init_viewe_len,
        .col_offset = OWL_CO5300_VIEWE_COL_OFFSET,
    };
    lv_display_t *disp = owl_amoled_display_create(&panel);

    /* The touch bus is I2C1; the always-on sensor bus will take I2C0. */
    const owl_amoled_touch_t touch = {
        .chip = OWL_TOUCH_CST816,
        .i2c_port = I2C_NUM_1,
        .pin_sda = OWL_PIN_TP_SDA,
        .pin_scl = OWL_PIN_TP_SCL,
        .pin_int = OWL_PIN_TP_INT,
        .int_pullup = false, /* 10k to DISP_3V3 on the board */
        .addr = OWL_I2C_ADDR_CST820,
        .scl_hz = 400000,
        .ready_at_us = released + OWL_TOUCH_RESET_WAIT_MS * 1000LL,
    };
    owl_amoled_touch_create(disp, &touch);
    return disp;
}

void bsp_status_led(uint8_t r, uint8_t g, uint8_t b)
{
    /* Rev A has no status LED. */
    (void)r;
    (void)g;
    (void)b;
}
