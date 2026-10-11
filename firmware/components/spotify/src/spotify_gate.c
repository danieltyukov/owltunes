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

/* Never shorten a block that is already longer. */
static void block_until(spotify_gate_t *g, int64_t until_ms)
{
    if (until_ms > g->blocked_until_ms) {
        g->blocked_until_ms = until_ms;
    }
}

static int64_t backoff_ms(uint8_t failures)
{
    int64_t delay = SPOTIFY_GATE_BACKOFF_FIRST_MS;
    for (uint8_t i = 1; i < failures && delay < SPOTIFY_GATE_BACKOFF_MAX_MS; i++) {
        delay *= 2;
    }
    return delay < SPOTIFY_GATE_BACKOFF_MAX_MS ? delay : SPOTIFY_GATE_BACKOFF_MAX_MS;
}

static int64_t quota_floor_s(uint8_t hits)
{
    int64_t floor_s = SPOTIFY_GATE_QUOTA_FIRST_S;
    for (uint8_t i = 1; i < hits && floor_s < SPOTIFY_GATE_QUOTA_MAX_S; i++) {
        floor_s *= 2;
    }
    return floor_s < SPOTIFY_GATE_QUOTA_MAX_S ? floor_s : SPOTIFY_GATE_QUOTA_MAX_S;
}

static void count_failure(spotify_gate_t *g)
{
    if (g->failures < UINT8_MAX) {
        g->failures++;
    }
}

spotify_outcome_t spotify_gate_record(spotify_gate_t *g, const spotify_error_t *err, int64_t now_ms)
{
    if (err == NULL || err->http_status == 0) {
        count_failure(g);
        block_until(g, now_ms + backoff_ms(g->failures));
        return SPOTIFY_OUTCOME_WAIT;
    }
    int64_t retry_after_s = err->retry_after_s;
    if (retry_after_s > SPOTIFY_GATE_RETRY_AFTER_MAX_S) {
        retry_after_s = SPOTIFY_GATE_RETRY_AFTER_MAX_S;
    }
    switch (err->kind) {
    case SPOTIFY_ERROR_NONE:
        g->failures = 0;
        g->quota_hits = 0;
        g->quota = false;
        return SPOTIFY_OUTCOME_OK;
    case SPOTIFY_ERROR_AUTH_EXPIRED:
        g->failures = 0;
        return SPOTIFY_OUTCOME_REFRESH;
    case SPOTIFY_ERROR_RATE_LIMITED:
        g->failures = 0;
        block_until(g, now_ms + (retry_after_s > 0 ? retry_after_s : 1) * 1000);
        return SPOTIFY_OUTCOME_WAIT;
    case SPOTIFY_ERROR_QUOTA_EXCEEDED: {
        g->failures = 0;
        if (g->quota_hits < UINT8_MAX) {
            g->quota_hits++;
        }
        int64_t wait_s = quota_floor_s(g->quota_hits);
        if (retry_after_s > wait_s) {
            wait_s = retry_after_s;
        }
        g->quota = true;
        block_until(g, now_ms + wait_s * 1000);
        return SPOTIFY_OUTCOME_WAIT;
    }
    case SPOTIFY_ERROR_SERVER: {
        count_failure(g);
        int64_t wait_ms = backoff_ms(g->failures);
        if (retry_after_s * 1000 > wait_ms) {
            wait_ms = retry_after_s * 1000;
        }
        block_until(g, now_ms + wait_ms);
        return SPOTIFY_OUTCOME_WAIT;
    }
    default:
        g->failures = 0;
        return SPOTIFY_OUTCOME_FAILED;
    }
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
