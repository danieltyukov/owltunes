/* Arduino Nano ESP32 (u-blox NORA-W106: ESP32-S3R8, 16 MB flash, 8 MB octal PSRAM). It has no
 * display: LVGL renders into a buffer in PSRAM and nothing is shown, so the owl's UI code runs on
 * the real chip next to Wi-Fi and TLS until a board with the AMOLED panel arrives. The RGB LED shows
 * the owl's status. */
#include "bsp.h"

#include <stdbool.h>

#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_system.h"
#include "owl_ui.h"

#define LINES 40

/* The RGB LED is common anode: a channel lights while its pin is low (the green LED lights while
 * GPIO0 is held low to enter download mode). Pins from Arduino's Nano ESP32 pinout.
 *
 * All three are strapping pins: GPIO0 (boot mode, the B1 jumper), GPIO45 (VDD_SPI voltage) and
 * GPIO46 (ROM log and boot mode). The chip samples straps only at power-on and after a hardware
 * reset, and it releases every IO driver on any chip reset before sampling, so a driven LED cannot
 * change what the next boot reads. A software restart does not sample straps again. Even so, the
 * shutdown handler below turns the LED off before esp_restart, so the pins are at their inactive
 * (high) level when the chip resets. */
static const gpio_num_t LED_PINS[3] = {GPIO_NUM_46, GPIO_NUM_0, GPIO_NUM_45}; /* red, green, blue */

static void discard(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map)
{
    (void)area;
    (void)px_map;
    lv_display_flush_ready(disp);
}

lv_display_t *bsp_display_init(void)
{
    const size_t size = OWL_UI_RES * LINES * sizeof(uint16_t);
    void *buf = heap_caps_malloc(size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    ESP_ERROR_CHECK(buf != NULL ? ESP_OK : ESP_ERR_NO_MEM);
    lv_display_t *disp = lv_display_create(OWL_UI_RES, OWL_UI_RES);
    lv_display_set_color_format(disp, LV_COLOR_FORMAT_RGB565);
    lv_display_set_buffers(disp, buf, NULL, size, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(disp, discard);
    return disp;
}

static void led_init(void)
{
    ledc_timer_config_t timer = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_8_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = 5000,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&timer));
    for (int i = 0; i < 3; i++) {
        ledc_channel_config_t channel = {
            .gpio_num = LED_PINS[i],
            .speed_mode = LEDC_LOW_SPEED_MODE,
            .channel = (ledc_channel_t)i,
            .timer_sel = LEDC_TIMER_0,
            .duty = 0,
            .hpoint = 0,
            .flags.output_invert = 1,
        };
        ESP_ERROR_CHECK(ledc_channel_config(&channel));
    }
}

static bool s_ready;

static void led_off(void)
{
    if (!s_ready) {
        return;
    }
    for (int i = 0; i < 3; i++) {
        ledc_set_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i, 0);
        ledc_update_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i);
    }
}

void bsp_status_led(uint8_t r, uint8_t g, uint8_t b)
{
    static int last[3] = {-1, -1, -1};
    if (!s_ready) {
        led_init();
        s_ready = true;
        ESP_ERROR_CHECK(esp_register_shutdown_handler(led_off));
    }
    const uint8_t want[3] = {r, g, b};
    for (int i = 0; i < 3; i++) {
        if (want[i] != last[i]) {
            ledc_set_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i, want[i]);
            ledc_update_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i);
            last[i] = want[i];
        }
    }
}
