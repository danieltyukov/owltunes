#include "sim_png.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "lvgl.h"

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_PNG
#include "stb_image.h"

bool sim_png_write_screen(const char *path)
{
    lv_obj_t *screen = lv_screen_active();
    lv_obj_update_layout(screen);
    lv_draw_buf_t *snap = lv_snapshot_take(screen, LV_COLOR_FORMAT_ARGB8888);
    if (snap == NULL) {
        return false;
    }
    uint32_t w = snap->header.w, h = snap->header.h, stride = snap->header.stride;
    uint8_t *rgba = malloc((size_t)w * h * 4);
    if (rgba == NULL) {
        lv_draw_buf_destroy(snap);
        return false;
    }
    double r = w / 2.0;
    for (uint32_t y = 0; y < h; y++) {
        for (uint32_t x = 0; x < w; x++) {
            const uint8_t *px = snap->data + (size_t)y * stride + (size_t)x * 4; /* B, G, R, A */
            uint8_t *o = rgba + ((size_t)y * w + x) * 4;
            double dx = x + 0.5 - r, dy = y + 0.5 - r;
            o[0] = px[2];
            o[1] = px[1];
            o[2] = px[0];
            o[3] = dx * dx + dy * dy <= r * r ? 255 : 0;
        }
    }
    int ok = stbi_write_png(path, (int)w, (int)h, 4, rgba, (int)w * 4);
    free(rgba);
    lv_draw_buf_destroy(snap);
    return ok != 0;
}

int sim_png_compare(const char *actual, const char *golden, int tolerance, double max_fraction)
{
    int aw, ah, gw, gh, channels;
    unsigned char *a = stbi_load(actual, &aw, &ah, &channels, 4);
    unsigned char *g = stbi_load(golden, &gw, &gh, &channels, 4);
    if (a == NULL || g == NULL) {
        fprintf(stderr, "cannot read %s or %s\n", actual, golden);
        stbi_image_free(a);
        stbi_image_free(g);
        return 2;
    }
    if (aw != gw || ah != gh) {
        fprintf(stderr, "%s is %dx%d but %s is %dx%d\n", actual, aw, ah, golden, gw, gh);
        stbi_image_free(a);
        stbi_image_free(g);
        return 1;
    }
    size_t total = (size_t)aw * (size_t)ah, bad = 0;
    for (size_t i = 0; i < total * 4; i += 4) {
        for (int c = 0; c < 4; c++) {
            if (abs((int)a[i + c] - (int)g[i + c]) > tolerance) {
                bad++;
                break;
            }
        }
    }
    stbi_image_free(a);
    stbi_image_free(g);
    double fraction = (double)bad / (double)total;
    printf("%s: %zu of %zu pixels differ (%.3f%%)\n", actual, bad, total, fraction * 100.0);
    return fraction > max_fraction ? 1 : 0;
}
