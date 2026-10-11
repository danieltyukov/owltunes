#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "owl_app.h"
#include "owl_model.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The one thing the owl most needs the person to know right now. A headless board shows it on
 * its RGB LED; the console reports it by name. */
typedef enum {
    OWL_STATUS_NEEDS_WIFI,   /* no Wi-Fi network saved */
    OWL_STATUS_JOINING,      /* networks saved, not online yet */
    OWL_STATUS_NEEDS_LOGIN,  /* online, no Spotify login saved */
    OWL_STATUS_LINKING,      /* exchanging a login code with Spotify */
    OWL_STATUS_LOG_IN_AGAIN, /* Spotify refused the saved login */
    OWL_STATUS_STARTING,     /* linked and online, no playback state yet */
    OWL_STATUS_QUOTA,        /* QUOTA_EXCEEDED: the Web API is off until Retry-After passes */
    OWL_STATUS_RATE_LIMITED, /* waiting for Retry-After or after server errors */
    OWL_STATUS_NO_DEVICE,    /* no active Spotify device */
    OWL_STATUS_PAUSED,
    OWL_STATUS_PLAYING,
} owl_status_t;

typedef struct {
    bool has_networks; /* at least one Wi-Fi network is saved */
    bool online;       /* the network is up */
    bool linked;       /* a Spotify login is saved */
    bool linking;      /* a login code is being exchanged */
    bool log_in_again; /* Spotify refused the saved login */
    owl_link_t link;   /* the Spotify runtime's link: OWL_LINK_BLE during a quota lockout */
    bool rate_limited; /* the runtime may not call the Web API yet */
    owl_player_status_t player;
} owl_status_inputs_t;

owl_status_t owl_status_of(const owl_status_inputs_t *in);

/* "needs_wifi", "joining", "needs_login", "linking", "log_in_again", "starting", "quota",
 * "rate_limited", "no_device", "paused" or "playing". */
const char *owl_status_name(owl_status_t s);

typedef struct {
    uint8_t r, g, b;
} owl_rgb_t;

#define OWL_LED_SLOW_PERIOD_MS 2000
#define OWL_LED_FAST_PERIOD_MS 500

/* The status LED colour at now_ms. Waiting for the person blinks slowly, waiting for the network
 * or Spotify blinks quickly, and steady states are solid. Levels stay low because the dev board's
 * LED is very bright. */
owl_rgb_t owl_status_led(owl_status_t s, int64_t now_ms);

#ifdef __cplusplus
}
#endif
