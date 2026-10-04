#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "owl_cmd.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OWL_CMDQ_CAP 8

/* Commands waiting to be sent to Spotify one at a time, oldest first. */
typedef struct {
    owl_cmd_t items[OWL_CMDQ_CAP];
    uint8_t head;
    uint8_t count;
} owl_cmdq_t;

void owl_cmdq_init(owl_cmdq_t *q);

/* Queue cmd, coalescing with what is already queued (see owl_cmdq.c). False when full. */
bool owl_cmdq_push(owl_cmdq_t *q, const owl_cmd_t *cmd);

bool owl_cmdq_pop(owl_cmdq_t *q, owl_cmd_t *out);

uint8_t owl_cmdq_count(const owl_cmdq_t *q);

#ifdef __cplusplus
}
#endif
