#include "sim_display.h"

#include "owl_ui.h"

static uint32_t s_now_ms;

static uint32_t tick_cb(void)
{
    return s_now_ms;
}

void sim_clock_set_ms(uint32_t ms)
{
    s_now_ms = ms;
}

static void flush_discard(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map)
{
    (void)area;
    (void)px_map;
    lv_display_flush_ready(disp);
}

lv_display_t *sim_display_create_headless(void)
{
    static uint32_t buf[OWL_UI_RES * 48]; /* 48 lines of 32-bit pixels, word aligned */
    lv_init();
    lv_tick_set_cb(tick_cb);
    lv_display_t *disp = lv_display_create(OWL_UI_RES, OWL_UI_RES);
    lv_display_set_buffers(disp, buf, NULL, sizeof buf, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(disp, flush_discard);
    return disp;
}
