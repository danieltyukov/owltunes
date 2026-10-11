#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Which saved Wi-Fi network to join, and when, as a pure state machine. The firmware feeds it
 * Wi-Fi events and carries out the step each call returns. Networks are tried in the order they
 * were saved (home first, then the phone hotspot). When every network has failed, the next round
 * starts after 5 s, then 10, 20 and 40 s, and from then on every 60 s. A dropped connection starts
 * a new round at once. */

#define OWL_WIFI_MAX_NETWORKS 4
#define OWL_WIFI_ATTEMPT_MS 20000
#define OWL_WIFI_BACKOFF_FIRST_MS 5000
#define OWL_WIFI_BACKOFF_MAX_MS 60000
#define OWL_WIFI_NEVER INT64_MAX

/* ESP-IDF disconnect reasons the plan tells apart (values from esp_wifi_types_generic.h; the
 * firmware checks at compile time that they still match). */
#define OWL_WIFI_REASON_AUTH_EXPIRE 2
#define OWL_WIFI_REASON_ASSOC_LEAVE 8
#define OWL_WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT 15
#define OWL_WIFI_REASON_NO_AP_FOUND 201
#define OWL_WIFI_REASON_AUTH_FAIL 202
#define OWL_WIFI_REASON_HANDSHAKE_TIMEOUT 204
#define OWL_WIFI_REASON_NO_AP_FOUND_W_COMPATIBLE_SECURITY 210
#define OWL_WIFI_REASON_NO_AP_FOUND_IN_AUTHMODE_THRESHOLD 211
#define OWL_WIFI_REASON_NO_AP_FOUND_IN_RSSI_THRESHOLD 212

typedef enum {
    OWL_WIFI_FAIL_NONE,
    OWL_WIFI_FAIL_NOT_FOUND,      /* the network is not in range, or its security is not supported */
    OWL_WIFI_FAIL_WRONG_PASSWORD, /* the handshake failed: almost always a wrong password */
    OWL_WIFI_FAIL_NO_ADDRESS,     /* nothing happened within OWL_WIFI_ATTEMPT_MS (no DHCP answer) */
    OWL_WIFI_FAIL_OTHER,
} owl_wifi_fail_t;

typedef enum {
    OWL_WIFI_IDLE,    /* no saved network */
    OWL_WIFI_JOINING, /* waiting for an address from networks[index] */
    OWL_WIFI_ONLINE,  /* joined networks[index] and got an address */
    OWL_WIFI_WAITING, /* every network failed: waiting for the next round */
} owl_wifi_state_t;

typedef enum {
    OWL_WIFI_DO_NOTHING,
    OWL_WIFI_DO_CONNECT, /* leave the current network, then join networks[index] */
    OWL_WIFI_DO_STOP,    /* leave the current network and stay off */
} owl_wifi_action_t;

typedef struct {
    owl_wifi_action_t action;
    uint8_t index;          /* OWL_WIFI_DO_CONNECT: the saved network to join */
    owl_wifi_fail_t failed; /* not NONE: the attempt on failed_index just failed; report it */
    uint8_t failed_index;
} owl_wifi_step_t;

typedef struct {
    owl_wifi_state_t state;
    uint8_t n_networks;
    uint8_t index;         /* JOINING or ONLINE: the network in use */
    uint8_t failed_rounds; /* rounds in a row in which every network failed */
    int64_t deadline_ms;   /* JOINING: give up on the attempt; WAITING: start the next round */
} owl_wifi_t;

void owl_wifi_init(owl_wifi_t *w);

/* The saved list changed. keep is the joined network's index in the new list when it is still
 * there with the same password, else -1. A working connection is kept; otherwise a new round
 * starts with the first network. No networks at all stops Wi-Fi. */
owl_wifi_step_t owl_wifi_set_networks(owl_wifi_t *w, uint8_t n_networks, int keep, int64_t now_ms);

owl_wifi_step_t owl_wifi_got_address(owl_wifi_t *w);

/* reason is the ESP-IDF disconnect reason. OWL_WIFI_REASON_ASSOC_LEAVE is the owl leaving on its
 * own (every OWL_WIFI_DO_CONNECT and OWL_WIFI_DO_STOP causes one) and is ignored. */
owl_wifi_step_t owl_wifi_disconnected(owl_wifi_t *w, int reason, int64_t now_ms);

/* Call when owl_wifi_deadline() has passed. */
owl_wifi_step_t owl_wifi_tick(owl_wifi_t *w, int64_t now_ms);

/* When owl_wifi_tick must run next, or OWL_WIFI_NEVER. */
int64_t owl_wifi_deadline(const owl_wifi_t *w);

owl_wifi_fail_t owl_wifi_classify(int reason);

/* The error code sent to the setup page: "wifi_not_found", "wifi_wrong_password",
 * "wifi_no_address" or "wifi_failed"; "" for OWL_WIFI_FAIL_NONE. */
const char *owl_wifi_fail_name(owl_wifi_fail_t f);

/* "idle", "joining", "online" or "waiting". */
const char *owl_wifi_state_name(owl_wifi_state_t s);

#ifdef __cplusplus
}
#endif
