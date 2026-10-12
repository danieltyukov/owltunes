#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "owl_app.h"
#include "owl_model.h"
#include "owl_shell.h"
#include "spotify_gate.h"

/* The Spotify runtime: while the owl is linked and online it polls the playback state on the budget
 * of spec section 9.4, sends player commands to the Web API one at a time, honours Retry-After,
 * backoffs and QUOTA_EXCEEDED, and reports everything on the console as JSON lines
 * (docs/console.md). It runs on core 0, next to Wi-Fi. */

typedef struct {
    bool active;     /* linked and online: the runtime talks to Spotify */
    owl_link_t link; /* OWL_LINK_API; OWL_LINK_BLE during a quota lockout; OWL_LINK_NONE when inactive */
    int32_t wait_s;  /* seconds until Spotify may be called again; 0 when it may, or when inactive */
    spotify_block_t block; /* why it may not (quota, rate_limited or backoff); NONE when inactive */
    owl_player_t player;
} spotify_task_view_t;

void spotify_task_start(void);

/* Hand a console command to the runtime (any task). False when its queue is full. */
bool spotify_task_post(const owl_shell_cmd_t *cmd);

/* The runtime's state now, for the UI and the status LED (any task). About 1.1 KB. */
void spotify_task_view(spotify_task_view_t *out);
