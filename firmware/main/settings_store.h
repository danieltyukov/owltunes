#pragma once

#include <stdbool.h>

#include "esp_err.h"
#include "owl_prov.h"

/* Initialise NVS, erasing it when it holds a layout this ESP-IDF cannot read. Call once at boot. */
esp_err_t settings_store_init(void);
/* Read the saved settings into s. False when nothing is stored or the blob has another size. */
bool settings_store_load(owl_settings_t *s);
esp_err_t settings_store_save(const owl_settings_t *s);
