#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "cJSON.h"
#include "owl_model.h"

/* NULL when key is missing or not a string. */
const char *sj_str(const cJSON *obj, const char *key);
bool sj_bool(const cJSON *obj, const char *key, bool fallback);
int64_t sj_int(const cJSON *obj, const char *key, int64_t fallback);
/* NULL when key is missing or not an object / array. */
const cJSON *sj_obj(const cJSON *obj, const char *key);
const cJSON *sj_arr(const cJSON *obj, const char *key);
/* URL of the image whose width is closest to want_px (ties prefer the larger); "" when none. */
const char *sj_pick_image(const cJSON *images, int want_px);
/* Join the "name" fields of an artists array with ", ", UTF-8 safe. */
void sj_join_names(const cJSON *artists, char *dst, size_t cap);
/* Fill t from a track or episode object. */
void sj_parse_track(const cJSON *item, owl_track_t *t);
