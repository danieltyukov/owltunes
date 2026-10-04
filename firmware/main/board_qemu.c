#include "board.h"

#include "esp_err.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_qemu_rgb.h"
#include "owl_ui.h"

static void flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map)
{
    esp_lcd_panel_handle_t panel = lv_display_get_user_data(disp);
    esp_lcd_panel_draw_bitmap(panel, area->x1, area->y1, area->x2 + 1, area->y2 + 1, px_map);
    lv_display_flush_ready(disp);
}

lv_display_t *board_display_init(void)
{
    static uint16_t buf[OWL_UI_RES * 40]; /* 40 lines of RGB565 */
    esp_lcd_panel_handle_t panel = NULL;
    esp_lcd_rgb_qemu_config_t config = {
        .width = OWL_UI_RES,
        .height = OWL_UI_RES,
        .bpp = RGB_QEMU_BPP_16,
    };
    ESP_ERROR_CHECK(esp_lcd_new_rgb_qemu(&config, &panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(panel));

    lv_display_t *disp = lv_display_create(OWL_UI_RES, OWL_UI_RES);
    lv_display_set_color_format(disp, LV_COLOR_FORMAT_RGB565);
    lv_display_set_buffers(disp, buf, NULL, sizeof buf, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_user_data(disp, panel);
    lv_display_set_flush_cb(disp, flush_cb);
    return disp;
}
