#include "owl_cmdq.h"

#include <string.h>

static owl_cmd_t *at(owl_cmdq_t *q, uint8_t i)
{
    return &q->items[(q->head + i) % OWL_CMDQ_CAP];
}

/* Commands where only the latest value matters, wherever they sit in the queue. */
static bool replace_anywhere(owl_cmd_type_t type)
{
    return type == OWL_CMD_VOLUME || type == OWL_CMD_SHUFFLE || type == OWL_CMD_REPEAT;
}

/* True when incoming undoes queued, so both can be dropped. */
static bool cancels(const owl_cmd_t *queued, const owl_cmd_t *incoming)
{
    switch (queued->type) {
    case OWL_CMD_PLAY:
        return incoming->type == OWL_CMD_PAUSE;
    case OWL_CMD_PAUSE:
        return incoming->type == OWL_CMD_PLAY;
    case OWL_CMD_LIKE:
        return incoming->type == OWL_CMD_UNLIKE && strcmp(queued->uri, incoming->uri) == 0;
    case OWL_CMD_UNLIKE:
        return incoming->type == OWL_CMD_LIKE && strcmp(queued->uri, incoming->uri) == 0;
    default:
        return false;
    }
}

void owl_cmdq_init(owl_cmdq_t *q)
{
    memset(q, 0, sizeof *q);
}

bool owl_cmdq_push(owl_cmdq_t *q, const owl_cmd_t *cmd)
{
    if (cmd->type == OWL_CMD_NONE) {
        return false;
    }
    if (replace_anywhere(cmd->type)) {
        for (uint8_t i = 0; i < q->count; i++) {
            if (at(q, i)->type == cmd->type) {
                *at(q, i) = *cmd;
                return true;
            }
        }
    }
    if (q->count > 0) {
        owl_cmd_t *last = at(q, (uint8_t)(q->count - 1));
        /* A seek only replaces a seek at the tail: an earlier one belongs to a different track. */
        if (cmd->type == OWL_CMD_SEEK && last->type == OWL_CMD_SEEK) {
            *last = *cmd;
            return true;
        }
        if (cancels(last, cmd)) {
            q->count--;
            return true;
        }
    }
    if (q->count == OWL_CMDQ_CAP) {
        return false;
    }
    *at(q, q->count) = *cmd;
    q->count++;
    return true;
}

bool owl_cmdq_pop(owl_cmdq_t *q, owl_cmd_t *out)
{
    if (q->count == 0) {
        return false;
    }
    *out = *at(q, 0);
    q->head = (uint8_t)((q->head + 1) % OWL_CMDQ_CAP);
    q->count--;
    return true;
}

uint8_t owl_cmdq_count(const owl_cmdq_t *q)
{
    return q->count;
}
