/* Host stand-in for FreeRTOS.h: what firmware/main/spotify_task.c and api_gate.c use. The host
 * tests run on one thread, so the locks do nothing. */
#pragma once

#include <assert.h>
#include <stdint.h>

typedef uint32_t TickType_t;
typedef int BaseType_t;

#define pdFALSE 0
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY 0xffffffffu
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms))
#define configASSERT(x) assert(x)

typedef int portMUX_TYPE;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(mux) ((void)(mux))
#define portEXIT_CRITICAL(mux) ((void)(mux))
