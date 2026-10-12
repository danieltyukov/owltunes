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

/* Why nothing may be sent right now. */
typedef enum {
    SPOTIFY_BLOCK_NONE,
    SPOTIFY_BLOCK_QUOTA,        /* QUOTA_EXCEEDED lockout: media keys only */
    SPOTIFY_BLOCK_RATE_LIMITED, /* 429 */
    SPOTIFY_BLOCK_BACKOFF,      /* server error or lost connection */
} spotify_block_t;

/* Counters of one endpoint. The Web API and the token endpoint keep their own, so an answer from
 * one never resets the other's streaks. */
typedef struct {
    uint8_t failures;   /* server errors or lost connections in a row; reset by a success only */
    uint8_t quota_hits; /* QUOTA_EXCEEDED answers; reset by a success only */
    uint8_t rate_hits;  /* 429 answers; reset by a success only */
    bool refresh_asked; /* a REFRESH was returned for the current 401 streak */
} spotify_gate_endpoint_t;

typedef struct {
    int64_t blocked_until_ms;      /* nothing is sent before this, whichever endpoint; 0 when open */
    bool quota;                    /* the current block is a QUOTA_EXCEEDED lockout */
    spotify_block_t block;         /* kind of the current block (see spotify_gate_block) */
    spotify_gate_endpoint_t web;   /* api.spotify.com */
    spotify_gate_endpoint_t token; /* accounts.spotify.com */
} spotify_gate_t;

void spotify_gate_init(spotify_gate_t *g);

bool spotify_gate_open(const spotify_gate_t *g, int64_t now_ms);

/* OWL_LINK_BLE during a quota lockout, else OWL_LINK_API. */
owl_link_t spotify_gate_link(const spotify_gate_t *g, int64_t now_ms);

/* Whole seconds until the gate opens, rounded up; 0 when it is open. */
int32_t spotify_gate_wait_s(const spotify_gate_t *g, int64_t now_ms);

/* Why the gate is closed at now_ms; SPOTIFY_BLOCK_NONE when it is open. */
spotify_block_t spotify_gate_block(const spotify_gate_t *g, int64_t now_ms);

/* "quota", "rate_limited" or "backoff", as the console's api and auth lines name a block; "" for
 * SPOTIFY_BLOCK_NONE. */
const char *spotify_block_name(spotify_block_t block);

/* Record one Web API answer. err is spotify_classify_error's verdict, or NULL when no answer arrived
 * (no connection, TLS failure, timeout). REFRESH is returned once per 401 streak: a 401 after the
 * refreshed request is FAILED, until a success or a successful token refresh. */
spotify_outcome_t spotify_gate_record(spotify_gate_t *g, const spotify_error_t *err, int64_t now_ms);

/* Record one answer from the token endpoint. Same blocking rules (Retry-After, backoff), but its
 * own counters, no quota lockout, and never REFRESH: a 401 there is an invalid client (FAILED).
 * A success re-arms REFRESH for the Web API. */
spotify_outcome_t spotify_gate_record_token(spotify_gate_t *g, const spotify_error_t *err, int64_t now_ms);

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
