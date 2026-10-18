#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "lvgl.h"
#include "owl_co5300.h"
#include "owl_touch.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The round CO5300 AMOLED and its touch controller as LVGL sees them, shared by the boards that carry
 * one (bsp_owltunes_reva, bsp_waveshare_amoled_175). The board powers the panel and releases its
 * resets first; these functions only talk to the chips. Call them from the task that runs LVGL.
 * The first-light options (OWL_LCD_BGR, OWL_TOUCH_SWAP_XY, OWL_TOUCH_MIRROR_X, OWL_TOUCH_MIRROR_Y)
 * are read here, so every board gets them. */

typedef struct {
    int pin_cs;
    int pin_clk;
    int pin_d0;
    int pin_d1;
    int pin_d2;
    int pin_d3;
    uint32_t pclk_hz;
    const owl_co5300_cmd_t *init; /* sent in order once the bus is up: the first panel command */
    size_t init_len;
    int32_t col_offset; /* panel RAM column of frame column 0 */
} owl_amoled_panel_t;

/* Bring up QSPI on SPI2 (FSPI), send the init table and return the 466 x 466 LVGL display: RGB565
 * sent high byte first, two partial draw buffers in DMA-capable internal RAM, every redrawn area
 * aligned to 2 pixels, and the next area rendered while the previous one is on the bus. Aborts on
 * failure, as a board without its display cannot do anything useful. */
lv_display_t *owl_amoled_display_create(const owl_amoled_panel_t *panel);

typedef enum {
    OWL_TOUCH_CST816,  /* CST816S family, such as the CST820 */
    OWL_TOUCH_CST9217, /* Hynitron CST9217 */
} owl_touch_chip_t;

typedef struct {
    owl_touch_chip_t chip;
    int i2c_port;
    int pin_sda;
    int pin_scl;
    int pin_int;     /* falling edge when the controller has a new report */
    bool int_pullup; /* use the internal pull-up on INT */
    uint8_t addr;
    uint32_t scl_hz;
    int64_t ready_at_us; /* esp_timer time before which the controller is still in its reset wait */
} owl_amoled_touch_t;

/* Create the I2C bus and the LVGL pointer for the touch controller. The controller is read after an
 * INT edge and, while a finger is down, at every input period until it reports the release. */
lv_indev_t *owl_amoled_touch_create(lv_display_t *disp, const owl_amoled_touch_t *touch);

#ifdef __cplusplus
}
#endif
