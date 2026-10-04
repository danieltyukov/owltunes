#pragma once

#include <stdint.h>

#include "lvgl.h"

/* Initialise LVGL with a fake clock and a display that renders but shows nothing. */
lv_display_t *sim_display_create_headless(void);
void sim_clock_set_ms(uint32_t ms);
