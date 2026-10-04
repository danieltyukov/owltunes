#pragma once

#include <stdint.h>

#include "owl_model.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    OWL_CMD_NONE = 0,
    OWL_CMD_PLAY,
    OWL_CMD_PAUSE,
    OWL_CMD_NEXT,
    OWL_CMD_PREV,
    OWL_CMD_SEEK,
    OWL_CMD_VOLUME,
    OWL_CMD_SHUFFLE,
    OWL_CMD_REPEAT,
    OWL_CMD_LIKE,
    OWL_CMD_UNLIKE,
    OWL_CMD_PLAY_CONTEXT,
    OWL_CMD_PLAY_URIS,
    OWL_CMD_TRANSFER,
    OWL_CMD_QUEUE_ADD,
} owl_cmd_type_t;

#define OWL_CMD_MAX_URIS 20

/* One Spotify player or library command. */
typedef struct {
    owl_cmd_type_t type;
    int32_t value;                            /* SEEK ms, VOLUME percent, SHUFFLE 0/1, REPEAT owl_repeat_t */
    char uri[OWL_URI_LEN];                    /* LIKE/UNLIKE/QUEUE_ADD item, PLAY_CONTEXT context, TRANSFER device id */
    char offset_uri[OWL_URI_LEN];             /* PLAY_CONTEXT: track to start at, empty for the start */
    uint8_t n_uris;                           /* PLAY_URIS */
    char uris[OWL_CMD_MAX_URIS][OWL_URI_LEN]; /* PLAY_URIS */
} owl_cmd_t;

/* Reset cmd and fill the common fields. uri may be NULL. */
void owl_cmd_set(owl_cmd_t *cmd, owl_cmd_type_t type, int32_t value, const char *uri);

/* Apply the expected result of cmd to the player straight away, so the screen reacts before
 * Spotify confirms. The next poll corrects anything that turned out differently. */
void owl_player_apply_optimistic(owl_player_t *p, const owl_cmd_t *cmd, int64_t now_ms);

#ifdef __cplusplus
}
#endif
