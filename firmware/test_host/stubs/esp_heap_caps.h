/* Host stand-in for ESP-IDF's esp_heap_caps.h: the test decides whether PSRAM is there. */
#pragma once

#include <stddef.h>
#include <stdint.h>

#define MALLOC_CAP_8BIT (1 << 2)
#define MALLOC_CAP_SPIRAM (1 << 10)

void *heap_caps_malloc(size_t size, uint32_t caps);
void *heap_caps_calloc(size_t n, size_t size, uint32_t caps);
