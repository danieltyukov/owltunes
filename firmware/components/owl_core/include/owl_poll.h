#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "owl_model.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OWL_POLL_NEVER (-1)
#define OWL_POLL_PLAYING_MS 4000
#define OWL_POLL_IDLE_MS 15000
#define OWL_POLL_AFTER_COMMAND_MS 500
#define OWL_POLL_TRACK_END_SLACK_MS 300
#define OWL_POLL_STANDBY_MIN_MS 60000

typedef struct {
    int64_t now_ms;
    bool asleep;               /* deep sleep is imminent: never poll */
    bool screen_on;            /* false in hot standby */
    owl_player_status_t status;
    uint32_t remaining_ms;     /* owl_player_remaining_ms(); 0 when unknown */
    int64_t last_poll_ms;      /* -1 before the first poll */
    int64_t last_command_ms;   /* -1 when no command has been sent */
    int64_t blocked_until_ms;  /* rate limit or quota lockout: no polling before this, 0 for none */
} owl_poll_inputs_t;

/* Milliseconds until the next playback-state poll, or OWL_POLL_NEVER. Implements the budget in
 * docs/design section 9.4. */
int64_t owl_poll_delay_ms(const owl_poll_inputs_t *in);

#ifdef __cplusplus
}
#endif
