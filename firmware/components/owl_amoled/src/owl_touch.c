#include "owl_touch.h"

static int clamp(int v, int lo, int hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

void owl_touch_map(owl_touch_orient_t orient, int res, int raw_x, int raw_y, int *x, int *y)
{
    int ax = clamp(raw_x, 0, res - 1);
    int ay = clamp(raw_y, 0, res - 1);
    if (orient.mirror_x) {
        ax = res - 1 - ax;
    }
    if (orient.mirror_y) {
        ay = res - 1 - ay;
    }
    if (orient.swap_xy) {
        int t = ax;
        ax = ay;
        ay = t;
    }
    *x = ax;
    *y = ay;
}

bool owl_cst816_point(const uint8_t regs[OWL_CST816_POINT_LEN], int *x, int *y)
{
    if ((regs[0] & 0x0F) == 0) {
        return false;
    }
    *x = ((regs[1] & 0x0F) << 8) | regs[2];
    *y = ((regs[3] & 0x0F) << 8) | regs[4];
    return true;
}

/* As esp_lcd_touch_cst9217 (Waveshare-ESP32-components) and SensorLib's TouchDrvCST92xx decode it. */
bool owl_cst9217_point(const uint8_t data[OWL_CST9217_POINT_LEN], int *x, int *y)
{
    if (data[6] != OWL_CST9217_ACK || (data[5] & 0x7F) == 0 || (data[0] & 0x0F) != 0x06) {
        return false;
    }
    *x = (data[1] << 4) | (data[3] >> 4);
    *y = (data[2] << 4) | (data[3] & 0x0F);
    return true;
}
