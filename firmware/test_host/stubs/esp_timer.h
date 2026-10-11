/* Host stand-in for ESP-IDF's esp_timer.h: the test sets the time. */
#pragma once

#include <stdint.h>

int64_t esp_timer_get_time(void);
