#include "spotify_gate.h"

#include <string.h>

void spotify_gate_init(spotify_gate_t *g)
{
    memset(g, 0, sizeof *g);
}

bool spotify_gate_open(const spotify_gate_t *g, int64_t now_ms)
{
    return now_ms >= g->blocked_until_ms;
}

owl_link_t spotify_gate_link(const spotify_gate_t *g, int64_t now_ms)
{
    return g->quota && !spotify_gate_open(g, now_ms) ? OWL_LINK_BLE : OWL_LINK_API;
}

int32_t spotify_gate_wait_s(const spotify_gate_t *g, int64_t now_ms)
{
    if (spotify_gate_open(g, now_ms)) {
        return 0;
    }
    return (int32_t)((g->blocked_until_ms - now_ms + 999) / 1000);
}

spotify_block_t spotify_gate_block(const spotify_gate_t *g, int64_t now_ms)
{
    return spotify_gate_open(g, now_ms) ? SPOTIFY_BLOCK_NONE : g->block;
}

const char *spotify_block_name(spotify_block_t block)
{
    switch (block) {
    case SPOTIFY_BLOCK_QUOTA:
        return "quota";
    case SPOTIFY_BLOCK_RATE_LIMITED:
        return "rate_limited";
    case SPOTIFY_BLOCK_BACKOFF:
        return "backoff";
    case SPOTIFY_BLOCK_NONE:
        break;
    }
    return "";
}

/* Block until until_ms of the given kind. A block never shortens a longer one, and the kind stays
 * that of the block that is actually in force. */
static void block_until(spotify_gate_t *g, int64_t until_ms, spotify_block_t kind)
{
    if (until_ms > g->blocked_until_ms) {
        g->blocked_until_ms = until_ms;
        g->block = kind;
        g->quota = kind == SPOTIFY_BLOCK_QUOTA;
    }
}

static int64_t doubled(int64_t first, int64_t max, uint8_t hits)
{
    int64_t value = first;
    for (uint8_t i = 1; i < hits && value < max; i++) {
        value *= 2;
    }
    return value < max ? value : max;
}

static void bump(uint8_t *counter)
{
    if (*counter < UINT8_MAX) {
        (*counter)++;
    }
}

static spotify_outcome_t record(spotify_gate_t *g, bool token, const spotify_error_t *err, int64_t now_ms)
{
    spotify_gate_endpoint_t *ep = token ? &g->token : &g->web;
    if (spotify_gate_open(g, now_ms)) {
        /* A lockout that has run out no longer describes the link. */
        g->block = SPOTIFY_BLOCK_NONE;
        g->quota = false;
    }
    if (err == NULL || err->http_status == 0) {
        bump(&ep->failures);
        block_until(
            g, now_ms + doubled(SPOTIFY_GATE_BACKOFF_FIRST_MS, SPOTIFY_GATE_BACKOFF_MAX_MS, ep->failures),
            SPOTIFY_BLOCK_BACKOFF);
        return SPOTIFY_OUTCOME_WAIT;
    }
    int64_t retry_after_s = err->retry_after_s;
    if (retry_after_s > SPOTIFY_GATE_RETRY_AFTER_MAX_S) {
        retry_after_s = SPOTIFY_GATE_RETRY_AFTER_MAX_S;
    }
    switch (err->kind) {
    case SPOTIFY_ERROR_NONE:
        memset(ep, 0, sizeof *ep);
        if (token) {
            g->web.refresh_asked = false;
        }
        return SPOTIFY_OUTCOME_OK;
    case SPOTIFY_ERROR_AUTH_EXPIRED:
        if (token || ep->refresh_asked) {
            return SPOTIFY_OUTCOME_FAILED;
        }
        ep->refresh_asked = true;
        return SPOTIFY_OUTCOME_REFRESH;
    case SPOTIFY_ERROR_RATE_LIMITED: {
        bump(&ep->rate_hits);
        /* Retries of a 429 that names no wait (classified as 5 s) get longer instead of staying at 5 s. */
        int64_t wait_s = retry_after_s > 0 ? retry_after_s : 1;
        if (ep->rate_hits > 1) {
            int64_t floor_s = doubled(5, SPOTIFY_GATE_BACKOFF_MAX_MS / 1000, ep->rate_hits);
            wait_s = wait_s > floor_s ? wait_s : floor_s;
        }
        block_until(g, now_ms + wait_s * 1000, SPOTIFY_BLOCK_RATE_LIMITED);
        return SPOTIFY_OUTCOME_WAIT;
    }
    case SPOTIFY_ERROR_QUOTA_EXCEEDED: {
        if (token) { /* the token endpoint has no quota lockout; treat it as a plain 429 */
            bump(&ep->rate_hits);
            block_until(g, now_ms + (retry_after_s > 0 ? retry_after_s : 1) * 1000,
                        SPOTIFY_BLOCK_RATE_LIMITED);
            return SPOTIFY_OUTCOME_WAIT;
        }
        bump(&ep->quota_hits);
        int64_t quota_s = doubled(SPOTIFY_GATE_QUOTA_FIRST_S, SPOTIFY_GATE_QUOTA_MAX_S, ep->quota_hits);
        if (retry_after_s > quota_s) {
            quota_s = retry_after_s;
        }
        block_until(g, now_ms + quota_s * 1000, SPOTIFY_BLOCK_QUOTA);
        return SPOTIFY_OUTCOME_WAIT;
    }
    case SPOTIFY_ERROR_SERVER: {
        bump(&ep->failures);
        int64_t wait_ms = doubled(SPOTIFY_GATE_BACKOFF_FIRST_MS, SPOTIFY_GATE_BACKOFF_MAX_MS, ep->failures);
        if (retry_after_s * 1000 > wait_ms) {
            wait_ms = retry_after_s * 1000;
        }
        block_until(g, now_ms + wait_ms, SPOTIFY_BLOCK_BACKOFF);
        return SPOTIFY_OUTCOME_WAIT;
    }
    default:
        return SPOTIFY_OUTCOME_FAILED;
    }
}

spotify_outcome_t spotify_gate_record(spotify_gate_t *g, const spotify_error_t *err, int64_t now_ms)
{
    return record(g, false, err, now_ms);
}

spotify_outcome_t spotify_gate_record_token(spotify_gate_t *g, const spotify_error_t *err, int64_t now_ms)
{
    return record(g, true, err, now_ms);
}

const char *spotify_error_name(spotify_error_kind_t kind)
{
    switch (kind) {
    case SPOTIFY_ERROR_AUTH_EXPIRED:
        return "auth";
    case SPOTIFY_ERROR_FORBIDDEN:
        return "forbidden";
    case SPOTIFY_ERROR_PREMIUM_REQUIRED:
        return "premium_required";
    case SPOTIFY_ERROR_NOT_FOUND:
        return "not_found";
    case SPOTIFY_ERROR_NO_ACTIVE_DEVICE:
        return "no_active_device";
    case SPOTIFY_ERROR_RATE_LIMITED:
        return "rate_limited";
    case SPOTIFY_ERROR_QUOTA_EXCEEDED:
        return "quota";
    case SPOTIFY_ERROR_SERVER:
        return "server_error";
    case SPOTIFY_ERROR_OTHER:
        return "rejected";
    case SPOTIFY_ERROR_NONE:
        break;
    }
    return "";
}

int32_t spotify_parse_retry_after(const char *value)
{
    if (value == NULL) {
        return -1;
    }
    while (*value == ' ' || *value == '\t') {
        value++;
    }
    if (*value < '0' || *value > '9') {
        return -1;
    }
    int64_t seconds = 0;
    for (; *value >= '0' && *value <= '9'; value++) {
        if (seconds < SPOTIFY_GATE_RETRY_AFTER_MAX_S) {
            seconds = seconds * 10 + (*value - '0');
        }
    }
    while (*value == ' ' || *value == '\t') {
        value++;
    }
    if (*value != '\0') {
        return -1;
    }
    return (int32_t)(seconds > SPOTIFY_GATE_RETRY_AFTER_MAX_S ? SPOTIFY_GATE_RETRY_AFTER_MAX_S : seconds);
}
