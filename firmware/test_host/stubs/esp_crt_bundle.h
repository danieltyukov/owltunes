/* Host stand-in for ESP-IDF's esp_crt_bundle.h. */
#pragma once

#include "esp_err.h"

esp_err_t esp_crt_bundle_attach(void *conf);
