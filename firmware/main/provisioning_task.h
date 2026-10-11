#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "owl_ui.h"

typedef struct {
    owl_ui_setup_mode_t mode;
    bool network_up;
    bool linked;        /* a Spotify login is saved */
    uint8_t n_networks; /* saved Wi-Fi networks */
    char error[64];     /* sentence for the setup screen, "" when there is none */
    uint32_t login_seq; /* changes whenever a new login replaces the saved one */
} provisioning_view_t;

/* Load the saved settings, hand the saved Wi-Fi networks to the network code and start the
 * protocol task. */
void provisioning_start(const char *name, const char *fw);
/* One console line that starts with OWL_PROV_PREFIX (console task). */
void provisioning_line(const char *line);
/* A network change from the board's network code (any task). Only the newest state is kept: the
 * protocol task reports it once it gets to it. */
void provisioning_network(bool up, const char *ip);
/* Joining a saved Wi-Fi network failed (any task); the setup page hears about it. */
void provisioning_network_failed(const char *ssid, const char *error);
/* What the setup screen shows now (any task). */
void provisioning_view(provisioning_view_t *out);

typedef enum {
    PROVISIONING_TOKEN_OK,
    PROVISIONING_TOKEN_NOT_LINKED, /* no Spotify login is saved */
    PROVISIONING_TOKEN_RETRY,      /* offline, Spotify unreachable, or the gate is closed (api_gate.h) */
    PROVISIONING_TOKEN_LOGGED_OUT, /* Spotify refused the saved login; the person must log in again */
    PROVISIONING_TOKEN_STORAGE,    /* a new or rotated login is not on flash yet: it is not used before */
} provisioning_token_t;

/* Copy a Spotify access token into out (SPOTIFY_ACCESS_TOKEN_LEN bytes) and its expiry (esp_timer
 * milliseconds) into expires_at_ms. The provisioning task keeps the token fresh by itself, a minute
 * before it expires; it refreshes first when the token is missing or about to expire, or when
 * force_refresh is set because Spotify just refused it, but only while the gate is open. A forced
 * request that could not refresh is RETRY, never the refused token again. Blocks up to timeout_ms
 * to hand the request over and as long again for the answer; one request at a time. The token is
 * never logged. Never call it from the provisioning task. */
provisioning_token_t provisioning_access_token(char *out, size_t cap, int64_t *expires_at_ms,
                                               bool force_refresh, uint32_t timeout_ms);
