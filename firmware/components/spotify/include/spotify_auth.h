#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "owl_crypto.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SPOTIFY_ACCOUNTS_HOST "accounts.spotify.com"
#define SPOTIFY_AUTHORIZE_URL "https://accounts.spotify.com/authorize"
#define SPOTIFY_TOKEN_PATH "/api/token"
#define SPOTIFY_SCOPES                                                                                       \
    "user-read-playback-state user-modify-playback-state user-read-currently-playing user-library-read "     \
    "user-library-modify playlist-read-private playlist-read-collaborative user-read-recently-played"

#define SPOTIFY_CLIENT_ID_LEN 33
#define SPOTIFY_REDIRECT_URI_LEN 160
#define SPOTIFY_VERIFIER_LEN 88  /* 86 characters from 64 random bytes */
#define SPOTIFY_CHALLENGE_LEN 44 /* 43 characters */
#define SPOTIFY_STATE_LEN 48     /* 22-character nonce, then "." and an IPv4 address */
#define SPOTIFY_CODE_LEN 1024    /* up to 1023 characters; Spotify sent 563 in October 2026 */
#define SPOTIFY_ACCESS_TOKEN_LEN 512
#define SPOTIFY_REFRESH_TOKEN_LEN 384
#define SPOTIFY_REFRESH_MARGIN_MS 60000
#define SPOTIFY_TOKEN_LIFETIME_MAX_S (24 * 3600) /* a longer expires_in is read as this */

bool spotify_client_id_valid(const char *s);
bool spotify_redirect_uri_valid(const char *s);
bool spotify_code_valid(const char *s);

/* One login attempt. The verifier never leaves the owl. */
typedef struct {
    char verifier[SPOTIFY_VERIFIER_LEN];
    char challenge[SPOTIFY_CHALLENGE_LEN];
    char state[SPOTIFY_STATE_LEN];
} spotify_pkce_t;

/* lan_ip (may be NULL) is appended to the state so the callback page can fall back to
 * http://<lan_ip>/callback when the setup tab is gone. */
void spotify_pkce_new(spotify_pkce_t *s, owl_random_fn random, const char *lan_ip);
bool spotify_state_matches(const spotify_pkce_t *s, const char *state);

bool spotify_authorize_url(const char *client_id, const char *redirect_uri, const spotify_pkce_t *s,
                           char *out, size_t cap);
bool spotify_token_body_for_code(const char *client_id, const char *redirect_uri, const char *code,
                                 const char *verifier, char *out, size_t cap);
bool spotify_token_body_for_refresh(const char *client_id, const char *refresh_token, char *out, size_t cap);

typedef struct {
    char access_token[SPOTIFY_ACCESS_TOKEN_LEN];
    char refresh_token[SPOTIFY_REFRESH_TOKEN_LEN];
    int64_t expires_at_ms;
} spotify_token_t;

typedef enum {
    SPOTIFY_TOKEN_OK,
    SPOTIFY_TOKEN_LOG_IN_AGAIN, /* invalid_grant: expired or revoked, the person must log in again */
    SPOTIFY_TOKEN_BAD_CLIENT,   /* invalid client ID or redirect URI */
    SPOTIFY_TOKEN_RETRY,        /* rate limit or server error: try later */
    SPOTIFY_TOKEN_BAD_RESPONSE, /* anything else */
} spotify_token_result_t;

/* Parse a response from POST /api/token. On success token gets the new access token and expiry;
 * its refresh token is replaced only when the response carries one (Spotify may rotate it). error
 * receives Spotify's error code ("invalid_grant") or "" on success. */
spotify_token_result_t spotify_parse_token_response(int http_status, const char *body, size_t len,
                                                    int64_t now_ms, spotify_token_t *token, char *error,
                                                    size_t error_cap);

/* True when there is no access token or it expires within SPOTIFY_REFRESH_MARGIN_MS. */
bool spotify_token_needs_refresh(const spotify_token_t *t, int64_t now_ms);

#ifdef __cplusplus
}
#endif
