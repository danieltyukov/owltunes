#pragma once

#include "lvgl.h"

/* Bring up this board's display and return the LVGL display bound to it. LVGL is initialised. */
lv_display_t *board_display_init(void);
