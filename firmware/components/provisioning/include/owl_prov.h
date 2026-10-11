#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "owl_crypto.h"
#include "spotify_auth.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OWL_PROV_PREFIX "@owl "
#define OWL_PROV_LINE_MAX 1024
#define OWL_PROV_PROTOCOL 1
#define OWL_PROV_MAX_NETWORKS 4
#define OWL_PROV_SESSION_MS (10 * 60 * 1000)
#define OWL_SSID_LEN 33
#define OWL_WIFI_PASSWORD_LEN 65
#define OWL_SETTINGS_VERSION 1

typedef struct {
    char ssid[OWL_SSID_LEN];
    char password[OWL_WIFI_PASSWORD_LEN];
} owl_wifi_network_t;

/* Everything that survives a reboot, stored as one blob. Bump OWL_SETTINGS_VERSION when the layout changes.
 */
typedef struct {
    uint32_t version;
    uint8_t n_networks;
    owl_wifi_network_t networks[OWL_PROV_MAX_NETWORKS];
    char client_id[SPOTIFY_CLIENT_ID_LEN];
    char redirect_uri[SPOTIFY_REDIRECT_URI_LEN];
    char refresh_token[SPOTIFY_REFRESH_TOKEN_LEN];
} owl_settings_t;

typedef enum {
    OWL_PROV_DO_SAVE = 1u << 0,      /* settings changed: persist them */
    OWL_PROV_DO_JOIN_WIFI = 1u << 1, /* the network list changed: (re)join */
    OWL_PROV_DO_EXCHANGE = 1u << 2,  /* a login code waits in owl_prov_t.code */
} owl_prov_action_t;

typedef enum {
    OWL_SETUP_STATE_NEEDS_WIFI,
    OWL_SETUP_STATE_NEEDS_SPOTIFY,
    OWL_SETUP_STATE_READY
} owl_setup_state_t;

typedef struct {
    owl_settings_t settings;
    char name[32];
    char fw[24];
    char ip[16];
    bool network_up;
    owl_random_fn random;
    spotify_pkce_t session;
    int64_t session_expires_ms; /* 0 when no login is in progress */
    char code[SPOTIFY_CODE_LEN];
    uint32_t actions;
} owl_prov_t;

void owl_settings_defaults(owl_settings_t *s);

/* saved may be NULL or from another settings version; then defaults are used. */
void owl_prov_init(owl_prov_t *p, const owl_settings_t *saved, const char *name, const char *fw,
                   owl_random_fn random);
void owl_prov_set_network(owl_prov_t *p, bool up, const char *ip);
owl_setup_state_t owl_prov_setup_state(const owl_prov_t *p);
const char *owl_prov_setup_state_name(owl_setup_state_t s);

/* Handle one console or Bluetooth line. Lines without OWL_PROV_PREFIX return false untouched (the
 * console also carries logs). Otherwise out receives exactly one response line ending in "\n". */
bool owl_prov_handle_line(owl_prov_t *p, const char *line, int64_t now_ms, char *out, size_t cap);

/* Accept a login code from any route. NULL on success (OWL_PROV_DO_EXCHANGE set), else an error code. */
const char *owl_prov_accept_code(owl_prov_t *p, const char *code, const char *state, int64_t now_ms);

/* Pending owl_prov_action_t bits; clears them. */
uint32_t owl_prov_take_actions(owl_prov_t *p);

/* Report the exchange result for owl_prov_t.code. Ends the login session either way. */
void owl_prov_finish_exchange(owl_prov_t *p, bool ok, const char *refresh_token);

/* Apply the result of refreshing the saved login. A rotated refresh token replaces the saved one;
 * LOG_IN_AGAIN and BAD_CLIENT forget it. True when the login was forgotten. */
bool owl_prov_apply_refresh(owl_prov_t *p, spotify_token_result_t result, const char *refresh_token);

struct cJSON;

/* Print obj as one protocol line ("@owl {...}\n", at most OWL_PROV_LINE_MAX bytes) and take
 * ownership of it. On failure (NULL obj, or it does not fit) out is "" and the result is false.
 * Shared with owl_shell, so every line on the console is framed the same way. */
bool owl_prov_emit(struct cJSON *obj, char *out, size_t cap);

/* Format an event line such as {"event":"spotify","state":"failed","error":"invalid_client"}. */
bool owl_prov_event(char *out, size_t cap, const char *event, const char *state, const char *key,
                    const char *value);

#ifdef __cplusplus
}
#endif
