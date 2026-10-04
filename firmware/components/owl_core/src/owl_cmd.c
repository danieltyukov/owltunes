#include "owl_cmd.h"

#include <string.h>

#include "owl_text.h"

void owl_cmd_set(owl_cmd_t *cmd, owl_cmd_type_t type, int32_t value, const char *uri)
{
    memset(cmd, 0, sizeof *cmd);
    cmd->type = type;
    cmd->value = value;
    owl_utf8_copy(cmd->uri, sizeof cmd->uri, uri);
}

static int32_t clamp(int32_t v, int32_t lo, int32_t hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

static void restart_at(owl_player_t *p, uint32_t position, int64_t now_ms)
{
    p->progress_ms = position;
    p->progress_at_ms = now_ms;
}

void owl_player_apply_optimistic(owl_player_t *p, const owl_cmd_t *cmd, int64_t now_ms)
{
    switch (cmd->type) {
    case OWL_CMD_PLAY:
        if (p->status == OWL_PLAYER_PAUSED) {
            p->progress_at_ms = now_ms;
            p->status = OWL_PLAYER_PLAYING;
        }
        break;
    case OWL_CMD_PAUSE:
        if (p->status == OWL_PLAYER_PLAYING) {
            restart_at(p, owl_player_progress_now(p, now_ms), now_ms);
            p->status = OWL_PLAYER_PAUSED;
        }
        break;
    case OWL_CMD_SEEK: {
        int32_t limit = p->track.duration_ms > 0 ? (int32_t)p->track.duration_ms : INT32_MAX;
        restart_at(p, (uint32_t)clamp(cmd->value, 0, limit), now_ms);
        break;
    }
    case OWL_CMD_VOLUME:
        p->device.volume_percent = (int8_t)clamp(cmd->value, 0, 100);
        break;
    case OWL_CMD_SHUFFLE:
        p->shuffle = cmd->value != 0;
        break;
    case OWL_CMD_REPEAT:
        p->repeat = (owl_repeat_t)clamp(cmd->value, OWL_REPEAT_OFF, OWL_REPEAT_TRACK);
        break;
    case OWL_CMD_LIKE:
    case OWL_CMD_UNLIKE:
        if (p->has_track && strcmp(cmd->uri, p->track.uri) == 0) {
            p->liked = cmd->type == OWL_CMD_LIKE;
            p->liked_known = true;
        }
        break;
    case OWL_CMD_NEXT:
    case OWL_CMD_PREV:
        restart_at(p, 0, now_ms);
        break;
    case OWL_CMD_PLAY_CONTEXT:
    case OWL_CMD_PLAY_URIS:
        owl_utf8_copy(p->context_uri, sizeof p->context_uri, cmd->type == OWL_CMD_PLAY_CONTEXT ? cmd->uri : "");
        restart_at(p, 0, now_ms);
        if (p->has_device) {
            p->status = OWL_PLAYER_PLAYING;
        }
        break;
    default:
        /* TRANSFER and QUEUE_ADD change nothing visible until the next poll. */
        break;
    }
}
