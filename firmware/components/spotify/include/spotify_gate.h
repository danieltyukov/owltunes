#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "owl_app.h"
#include "spotify_parse.h"

#ifdef __cplusplus
extern "C" {
#endif

/* When the owl may call the Web API again, decided from the answers it got (spec sections 5.6 and
 * 9.4). Retry-After is always honoured. QUOTA_EXCEEDED also switches the owl to media-key-only
 * (BLE) mode until it expires, and waits at least a minute, doubling for every lockout in a row
 * up to six hours, because a lockout without a usable Retry-After must not turn into a retry loop.
 * Server errors and lost connections back off from 2 s to 60 s. A 401 asks for one token refresh.
 * Answers from the token endpoint (accounts.spotify.com) go through the same gate, so their
 * Retry-After is honoured too. */

#define SPOTIFY_GATE_BACKOFF_FIRST_MS 2000
#define SPOTIFY_GATE_BACKOFF_MAX_MS 60000
#define SPOTIFY_GATE_QUOTA_FIRST_S 60
#define SPOTIFY_GATE_QUOTA_MAX_S (6 * 3600)
#define SPOTIFY_GATE_RETRY_AFTER_MAX_S (24 * 3600)

typedef enum {
    SPOTIFY_OUTCOME_OK,      /* 2xx: use the answer */
    SPOTIFY_OUTCOME_REFRESH, /* 401: get a fresh access token and send the same request once more */
    SPOTIFY_OUTCOME_WAIT,    /* 429, 5xx or no answer: nothing may be sent before the gate opens */
    SPOTIFY_OUTCOME_FAILED,  /* any other error: report it; sending it again will not help */
} spotify_outcome_t;

typedef struct {
    int64_t blocked_until_ms; /* nothing is sent before this; 0 when open */
    bool quota;               /* the block is a QUOTA_EXCEEDED lockout */
    uint8_t failures;         /* server errors or lost connections in a row */
    uint8_t quota_hits;       /* QUOTA_EXCEEDED answers in a row */
} spotify_gate_t;

void spotify_gate_init(spotify_gate_t *g);

bool spotify_gate_open(const spotify_gate_t *g, int64_t now_ms);

/* OWL_LINK_BLE during a quota lockout, else OWL_LINK_API. */
owl_link_t spotify_gate_link(const spotify_gate_t *g, int64_t now_ms);

/* Whole seconds until the gate opens, rounded up; 0 when it is open. */
int32_t spotify_gate_wait_s(const spotify_gate_t *g, int64_t now_ms);

/* Record one answer. err is spotify_classify_error's verdict, or NULL when no answer arrived
 * (no connection, TLS failure, timeout). */
spotify_outcome_t spotify_gate_record(spotify_gate_t *g, const spotify_error_t *err, int64_t now_ms);

/* The error code the console reports for an error: "auth", "forbidden", "premium_required",
 * "not_found", "no_active_device", "rate_limited", "quota", "server_error" or "rejected";
 * "" for SPOTIFY_ERROR_NONE. */
const char *spotify_error_name(spotify_error_kind_t kind);

/* A Retry-After header in seconds: -1 when it is missing or not a plain number (Spotify does not
 * send the HTTP-date form), capped at SPOTIFY_GATE_RETRY_AFTER_MAX_S. */
int32_t spotify_parse_retry_after(const char *value);

#ifdef __cplusplus
}
#endif
