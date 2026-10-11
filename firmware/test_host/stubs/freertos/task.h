/* Host stand-in for FreeRTOS task.h: the test never starts the task, it calls its steps. */
#pragma once

#include "freertos/FreeRTOS.h"

typedef void (*TaskFunction_t)(void *arg);
typedef void *TaskHandle_t;

BaseType_t xTaskCreatePinnedToCore(TaskFunction_t fn, const char *name, uint32_t stack, void *arg,
                                   uint32_t priority, TaskHandle_t *handle, BaseType_t core);
