#include "owl_status.h"

owl_status_t owl_status_of(const owl_status_inputs_t *in)
{
    if (in->linking) {
        return OWL_STATUS_LINKING;
    }
    if (!in->has_networks) {
        return OWL_STATUS_NEEDS_WIFI;
    }
    if (!in->online) {
        return OWL_STATUS_JOINING;
    }
    if (!in->linked) {
        return in->log_in_again ? OWL_STATUS_LOG_IN_AGAIN : OWL_STATUS_NEEDS_LOGIN;
    }
    if (in->link == OWL_LINK_BLE) {
        return OWL_STATUS_QUOTA;
    }
    if (in->rate_limited) {
        return OWL_STATUS_RATE_LIMITED;
    }
    switch (in->player) {
    case OWL_PLAYER_NO_DEVICE:
        return OWL_STATUS_NO_DEVICE;
    case OWL_PLAYER_PAUSED:
        return OWL_STATUS_PAUSED;
    case OWL_PLAYER_PLAYING:
        return OWL_STATUS_PLAYING;
    case OWL_PLAYER_UNKNOWN:
        break;
    }
    return OWL_STATUS_STARTING;
}

const char *owl_status_name(owl_status_t s)
{
    switch (s) {
    case OWL_STATUS_NEEDS_WIFI:
        return "needs_wifi";
    case OWL_STATUS_JOINING:
        return "joining";
    case OWL_STATUS_NEEDS_LOGIN:
        return "needs_login";
    case OWL_STATUS_LINKING:
        return "linking";
    case OWL_STATUS_LOG_IN_AGAIN:
        return "log_in_again";
    case OWL_STATUS_STARTING:
        return "starting";
    case OWL_STATUS_QUOTA:
        return "quota";
    case OWL_STATUS_RATE_LIMITED:
        return "rate_limited";
    case OWL_STATUS_NO_DEVICE:
        return "no_device";
    case OWL_STATUS_PAUSED:
        return "paused";
    case OWL_STATUS_PLAYING:
        return "playing";
    }
    return "starting";
}

typedef enum { SOLID, SLOW, FAST } pattern_t;

static const owl_rgb_t BLUE = {0, 0, 64};
static const owl_rgb_t AMBER = {64, 20, 0};
static const owl_rgb_t CYAN = {0, 40, 40};
static const owl_rgb_t RED = {64, 0, 0};
static const owl_rgb_t GREEN = {0, 48, 0};
static const owl_rgb_t DIM_GREEN = {0, 8, 0};
static const owl_rgb_t MAGENTA = {40, 0, 40};

owl_rgb_t owl_status_led(owl_status_t s, int64_t now_ms)
{
    owl_rgb_t colour = GREEN;
    pattern_t pattern = SOLID;
    switch (s) {
    case OWL_STATUS_NEEDS_WIFI:
        colour = BLUE;
        pattern = SLOW;
        break;
    case OWL_STATUS_JOINING:
        colour = BLUE;
        pattern = FAST;
        break;
    case OWL_STATUS_NEEDS_LOGIN:
        colour = AMBER;
        pattern = SLOW;
        break;
    case OWL_STATUS_LINKING:
        colour = CYAN;
        pattern = FAST;
        break;
    case OWL_STATUS_LOG_IN_AGAIN:
        colour = RED;
        pattern = SLOW;
        break;
    case OWL_STATUS_STARTING:
        colour = GREEN;
        pattern = FAST;
        break;
    case OWL_STATUS_QUOTA:
        colour = MAGENTA;
        break;
    case OWL_STATUS_RATE_LIMITED:
        colour = MAGENTA;
        pattern = SLOW;
        break;
    case OWL_STATUS_NO_DEVICE:
        colour = AMBER;
        break;
    case OWL_STATUS_PAUSED:
        colour = DIM_GREEN;
        break;
    case OWL_STATUS_PLAYING:
        colour = GREEN;
        break;
    }
    if (pattern != SOLID) {
        int64_t period = pattern == SLOW ? OWL_LED_SLOW_PERIOD_MS : OWL_LED_FAST_PERIOD_MS;
        int64_t phase = now_ms % period;
        if (phase < 0) {
            phase += period;
        }
        if (phase >= period / 2) {
            colour = (owl_rgb_t){0, 0, 0};
        }
    }
    return colour;
}
