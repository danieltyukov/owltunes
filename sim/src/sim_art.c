#include "sim_art.h"

#include <stdint.h>

const lv_image_dsc_t *sim_art_for(const char *uri)
{
    static lv_draw_buf_t *buf;
    if (buf == NULL) {
        buf = lv_draw_buf_create(SIM_ART_SIZE, SIM_ART_SIZE, LV_COLOR_FORMAT_XRGB8888, 0);
    }
    uint32_t h = 2166136261u; /* FNV-1a */
    for (const char *p = uri ? uri : ""; *p; p++) {
        h = (h ^ (uint8_t)*p) * 16777619u;
    }
    int r0 = 30 + (int)(h & 0x3F), g0 = 20 + (int)((h >> 6) & 0x3F), b0 = 60 + (int)((h >> 12) & 0x7F);
    int r1 = 200, g1 = 120 + (int)((h >> 19) & 0x3F), b1 = 40;
    for (int y = 0; y < SIM_ART_SIZE; y++) {
        for (int x = 0; x < SIM_ART_SIZE; x++) {
            int t = (x + y) * 255 / (2 * (SIM_ART_SIZE - 1));
            int r = r0 + (r1 - r0) * t / 255, g = g0 + (g1 - g0) * t / 255, b = b0 + (b1 - b0) * t / 255;
            int dx = x - 150, dy = y - 66;
            if (dx * dx + dy * dy <= 34 * 34) { /* a moon */
                r = 244;
                g = 237;
                b = 225;
            }
            uint8_t *px = buf->data + (size_t)y * buf->header.stride + (size_t)x * 4;
            px[0] = (uint8_t)b;
            px[1] = (uint8_t)g;
            px[2] = (uint8_t)r;
            px[3] = 255;
        }
    }
    return (const lv_image_dsc_t *)buf;
}
