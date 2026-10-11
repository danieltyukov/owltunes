/* Arduino Nano ESP32 (u-blox NORA-W106: ESP32-S3R8, 16 MB flash, 8 MB octal PSRAM). It has no
 * display: LVGL renders into a buffer in PSRAM and nothing is shown, so the owl's UI code runs on
 * the real chip next to Wi-Fi and TLS until a board with the AMOLED panel arrives. */
#include "bsp.h"

#include "esp_err.h"
#include "esp_heap_caps.h"
#include "owl_ui.h"

#define LINES 40

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
