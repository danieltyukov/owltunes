#include "owl_wifi.h"

#include <string.h>

static owl_wifi_step_t nothing(void)
{
    owl_wifi_step_t step = {.action = OWL_WIFI_DO_NOTHING, .failed = OWL_WIFI_FAIL_NONE};
    return step;
}

static owl_wifi_step_t join(owl_wifi_t *w, uint8_t index, int64_t now_ms)
{
    w->state = OWL_WIFI_JOINING;
    w->index = index;
    w->deadline_ms = now_ms + OWL_WIFI_ATTEMPT_MS;
    owl_wifi_step_t step = nothing();
    step.action = OWL_WIFI_DO_CONNECT;
    step.index = index;
    return step;
}

static int64_t backoff_ms(uint8_t failed_rounds)
{
    int64_t delay = OWL_WIFI_BACKOFF_FIRST_MS;
    for (uint8_t i = 1; i < failed_rounds && delay < OWL_WIFI_BACKOFF_MAX_MS; i++) {
        delay *= 2;
    }
    return delay < OWL_WIFI_BACKOFF_MAX_MS ? delay : OWL_WIFI_BACKOFF_MAX_MS;
}

/* The attempt on w->index failed: try the next network, or wait for the next round. */
static owl_wifi_step_t give_up(owl_wifi_t *w, owl_wifi_fail_t failure, int64_t now_ms)
{
    uint8_t failed_index = w->index;
    owl_wifi_step_t step;
    if (w->index + 1 < w->n_networks) {
        step = join(w, (uint8_t)(w->index + 1), now_ms);
    } else {
        if (w->failed_rounds < UINT8_MAX) {
            w->failed_rounds++;
        }
        w->state = OWL_WIFI_WAITING;
        w->deadline_ms = now_ms + backoff_ms(w->failed_rounds);
        step = nothing();
        step.action = OWL_WIFI_DO_STOP;
    }
    step.failed = failure;
    step.failed_index = failed_index;
    return step;
}

void owl_wifi_init(owl_wifi_t *w)
{
    memset(w, 0, sizeof *w);
    w->state = OWL_WIFI_IDLE;
}

owl_wifi_step_t owl_wifi_set_networks(owl_wifi_t *w, uint8_t n_networks, int keep, int64_t now_ms)
{
    bool was_connected = w->state == OWL_WIFI_JOINING || w->state == OWL_WIFI_ONLINE;
    w->n_networks = n_networks > OWL_WIFI_MAX_NETWORKS ? OWL_WIFI_MAX_NETWORKS : n_networks;
    w->failed_rounds = 0;
    if (w->n_networks == 0) {
        w->state = OWL_WIFI_IDLE;
        w->expect_leave = was_connected;
        owl_wifi_step_t step = nothing();
        step.action = OWL_WIFI_DO_STOP;
        return step;
    }
    if (w->state == OWL_WIFI_ONLINE && keep >= 0 && keep < w->n_networks) {
        w->index = (uint8_t)keep;
        return nothing();
    }
    w->expect_leave = was_connected;
    return join(w, 0, now_ms);
}

owl_wifi_step_t owl_wifi_got_address(owl_wifi_t *w)
{
    if (w->state == OWL_WIFI_JOINING) {
        w->state = OWL_WIFI_ONLINE;
        w->failed_rounds = 0;
    }
    return nothing();
}

owl_wifi_step_t owl_wifi_disconnected(owl_wifi_t *w, int reason, int64_t now_ms)
{
    bool expected = w->expect_leave;
    w->expect_leave = false;
    if (expected && reason == OWL_WIFI_REASON_ASSOC_LEAVE) {
        return nothing();
    }
    if (w->state == OWL_WIFI_JOINING) {
        return give_up(w, owl_wifi_classify(reason), now_ms);
    }
    if (w->state == OWL_WIFI_ONLINE) {
        return join(w, 0, now_ms);
    }
    return nothing();
}

owl_wifi_step_t owl_wifi_tick(owl_wifi_t *w, int64_t now_ms)
{
    if (w->state == OWL_WIFI_JOINING && now_ms >= w->deadline_ms) {
        w->expect_leave = true;
        return give_up(w, OWL_WIFI_FAIL_NO_ADDRESS, now_ms);
    }
    if (w->state == OWL_WIFI_WAITING && now_ms >= w->deadline_ms) {
        return join(w, 0, now_ms);
    }
    return nothing();
}

int64_t owl_wifi_deadline(const owl_wifi_t *w)
{
    if (w->state == OWL_WIFI_JOINING || w->state == OWL_WIFI_WAITING) {
        return w->deadline_ms;
    }
    return OWL_WIFI_NEVER;
}

owl_wifi_fail_t owl_wifi_classify(int reason)
{
    switch (reason) {
    case OWL_WIFI_REASON_NO_AP_FOUND:
    case OWL_WIFI_REASON_NO_AP_FOUND_W_COMPATIBLE_SECURITY:
    case OWL_WIFI_REASON_NO_AP_FOUND_IN_AUTHMODE_THRESHOLD:
    case OWL_WIFI_REASON_NO_AP_FOUND_IN_RSSI_THRESHOLD:
        return OWL_WIFI_FAIL_NOT_FOUND;
    case OWL_WIFI_REASON_AUTH_EXPIRE:
    case OWL_WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:
    case OWL_WIFI_REASON_AUTH_FAIL:
    case OWL_WIFI_REASON_HANDSHAKE_TIMEOUT:
        return OWL_WIFI_FAIL_WRONG_PASSWORD;
    default:
        return OWL_WIFI_FAIL_OTHER;
    }
}

const char *owl_wifi_fail_name(owl_wifi_fail_t f)
{
    switch (f) {
    case OWL_WIFI_FAIL_NOT_FOUND:
        return "wifi_not_found";
    case OWL_WIFI_FAIL_WRONG_PASSWORD:
        return "wifi_wrong_password";
    case OWL_WIFI_FAIL_NO_ADDRESS:
        return "wifi_no_address";
    case OWL_WIFI_FAIL_OTHER:
        return "wifi_failed";
    case OWL_WIFI_FAIL_NONE:
        break;
    }
    return "";
}

const char *owl_wifi_state_name(owl_wifi_state_t s)
{
    switch (s) {
    case OWL_WIFI_JOINING:
        return "joining";
    case OWL_WIFI_ONLINE:
        return "online";
    case OWL_WIFI_WAITING:
        return "waiting";
    case OWL_WIFI_IDLE:
        break;
    }
    return "idle";
}
