#pragma once

#include "lvgl.h"

/* What the firmware needs from a board. Every board has one bsp_<board> component under
 * firmware/boards/, built only when the OWL_BOARD Kconfig choice selects that board. */

/* Bring up the display and return the LVGL display bound to it; LVGL is initialised. A board
 * without a panel returns a display that renders into memory and shows nothing, so the same UI
 * code runs on every board. */
lv_display_t *bsp_display_init(void);
