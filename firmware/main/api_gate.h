#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "spotify_gate.h"

/* The owl's one Spotify gate (spotify_gate.h). The provisioning task records every answer from the
 * token endpoint (spotify_link.c) and the Spotify runtime will record its Web API answers, so a
 * Retry-After, a quota lockout or a backoff from either host holds back requests to both. Any task:
 * a spinlock guards it, and nothing inside it blocks or logs. */

/* Record one token endpoint answer; err is NULL when no answer arrived. */
spotify_outcome_t api_gate_record_token(const spotify_error_t *err, int64_t now_ms);

/* A copy of the gate, for spotify_gate_open, spotify_gate_block, spotify_gate_wait_s and
 * spotify_gate_link. */
void api_gate_get(spotify_gate_t *out);

/* True when a request may go out at now_ms. */
bool api_gate_open(int64_t now_ms);
