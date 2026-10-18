#include "owl_co5300.h"

uint32_t owl_co5300_cmd_word(uint8_t opcode, uint8_t cmd)
{
    return ((uint32_t)opcode << 24) | ((uint32_t)cmd << 8);
}

static void put_range(uint8_t out[4], int32_t first, int32_t last)
{
    out[0] = (uint8_t)((first >> 8) & 0xFF);
    out[1] = (uint8_t)(first & 0xFF);
    out[2] = (uint8_t)((last >> 8) & 0xFF);
    out[3] = (uint8_t)(last & 0xFF);
}

void owl_co5300_window(int32_t x1, int32_t y1, int32_t x2, int32_t y2, int32_t col_offset,
                       owl_co5300_window_t *out)
{
    put_range(out->caset, x1 + col_offset, x2 + col_offset);
    put_range(out->raset, y1, y2);
}

void owl_co5300_round_area(int32_t *x1, int32_t *y1, int32_t *x2, int32_t *y2)
{
    *x1 &= ~(int32_t)1;
    *y1 &= ~(int32_t)1;
    *x2 |= 1;
    *y2 |= 1;
}

/* The text sequence in VIEWE's init code (email of 17 October 2026). The C array in the same file ends
 * the CASET at 01 DD (472 columns), a typo: 01 D7 is column 471, so 466 columns from column 6. The
 * text sends FE and 35 with one parameter each, as the CO5300 command set has them. The C array also
 * waits 10 ms after 35, 53, 51 and 63; those waits are left out here, following the text. If the
 * panel misbehaves at first light, adding them back is the first thing to try. */
const owl_co5300_cmd_t owl_co5300_init_viewe[] = {
    {0xFE, 1, {0x00}, 0},                   /* user command page */
    {0xC4, 1, {0x80}, 0},                   /* SPI mode */
    {0x3A, 1, {0x55}, 0},                   /* RGB565 */
    {0x35, 1, {0x00}, 0},                   /* tearing effect on, V-blank only */
    {0x53, 1, {0x20}, 0},                   /* brightness control on */
    {0x51, 1, {0xFF}, 0},                   /* brightness */
    {0x63, 1, {0xFF}, 0},                   /* HBM brightness */
    {0x2A, 4, {0x00, 0x06, 0x01, 0xD7}, 0}, /* columns 6 to 471 */
    {0x2B, 4, {0x00, 0x00, 0x01, 0xD1}, 0}, /* rows 0 to 465 */
    {0x11, 0, {0}, 60},                     /* sleep out */
    {0x29, 0, {0}, 0},                      /* display on */
};
const size_t owl_co5300_init_viewe_len = sizeof owl_co5300_init_viewe / sizeof owl_co5300_init_viewe[0];

/* lcd_init_cmds in Waveshare's BSP (esp32_s3_touch_amoled_1_75.c, version 3.0.1), delays included:
 * three vendor registers on page 0x20 first, then the same sequence as VIEWE's. */
const owl_co5300_cmd_t owl_co5300_init_waveshare_175[] = {
    {0xFE, 1, {0x20}, 0},
    {0x19, 1, {0x10}, 0},
    {0x1C, 1, {0xA0}, 0},
    {0xFE, 1, {0x00}, 0},
    {0xC4, 1, {0x80}, 0},
    {0x3A, 1, {0x55}, 0},
    {0x35, 1, {0x00}, 0},
    {0x53, 1, {0x20}, 0},
    {0x51, 1, {0xFF}, 0},
    {0x63, 1, {0xFF}, 0},
    {0x2A, 4, {0x00, 0x06, 0x01, 0xD7}, 0},
    {0x2B, 4, {0x00, 0x00, 0x01, 0xD1}, 600},
    {0x11, 0, {0}, 600},
    {0x29, 0, {0}, 0},
};
const size_t owl_co5300_init_waveshare_175_len =
    sizeof owl_co5300_init_waveshare_175 / sizeof owl_co5300_init_waveshare_175[0];
