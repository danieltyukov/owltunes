#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Touch controllers next to the CO5300 panels: decoding their point registers and mapping a raw
 * point onto the frame. Pure logic, tested on the host. */

/* How the controller's axes sit against the frame. The mirrors act on the controller's own axes and
 * the swap comes after them, the order esp_lcd_touch uses. */
typedef struct {
    bool swap_xy;
    bool mirror_x;
    bool mirror_y;
} owl_touch_orient_t;

/* Map a raw point onto a res x res frame: clamp each axis to 0 to res - 1, mirror, then swap.
 * owl_amoled logs every raw point and its mapping at debug level ("touch raw x,y -> x,y"). */
void owl_touch_map(owl_touch_orient_t orient, int res, int raw_x, int raw_y, int *x, int *y);

/* CST816S family (the CST820 on rev A): five registers from 0x02, the finger count, then X and Y
 * with the high four bits of each in the low nibble of its first byte. True with the point when a
 * finger is down. */
#define OWL_CST816_REG_POINT 0x02
#define OWL_CST816_POINT_LEN 5
bool owl_cst816_point(const uint8_t regs[OWL_CST816_POINT_LEN], int *x, int *y);

/* CST9217 (the Waveshare kit): ten bytes read after writing the register address 0xD000. Byte 6 is
 * the 0xAB acknowledge, the low seven bits of byte 5 the finger count, and the first finger's
 * status nibble is 6 while it is down. True with the first finger's point when it is down. */
#define OWL_CST9217_REG_POINT 0xD000
#define OWL_CST9217_POINT_LEN 10
#define OWL_CST9217_ACK 0xAB
bool owl_cst9217_point(const uint8_t data[OWL_CST9217_POINT_LEN], int *x, int *y);

#ifdef __cplusplus
}
#endif
