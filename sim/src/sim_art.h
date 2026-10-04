#pragma once

#include "lvgl.h"

#define SIM_ART_SIZE 216

/* Deterministic stand-in for album art, seeded by the track URI (no real artwork in the repo). */
const lv_image_dsc_t *sim_art_for(const char *uri);
