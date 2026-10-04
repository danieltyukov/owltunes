#pragma once

#include <stdbool.h>

#include "owl_app.h"
#include "owl_cmd.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { SPOTIFY_GET, SPOTIFY_PUT, SPOTIFY_POST, SPOTIFY_DELETE } spotify_method_t;

#define SPOTIFY_API_HOST "api.spotify.com"
#define SPOTIFY_PATH_LEN 384
#define SPOTIFY_BODY_LEN 1536

typedef struct {
    spotify_method_t method;
    char path[SPOTIFY_PATH_LEN]; /* starts with /v1/ */
    char body[SPOTIFY_BODY_LEN]; /* JSON, empty when the request has no body */
} spotify_request_t;

/* Build the Web API request for a player or library command. False when the command cannot be
 * expressed safely (unknown type, out-of-range value, unexpected characters in a URI or id). */
bool spotify_request_for_command(const owl_cmd_t *cmd, spotify_request_t *out);

/* Build the request for a list fetch. */
bool spotify_request_for_fetch(const owl_fetch_t *fetch, spotify_request_t *out);

/* GET /v1/me/player, asking for podcast episodes too. */
void spotify_request_player_state(spotify_request_t *out);

const char *spotify_method_name(spotify_method_t m);

#ifdef __cplusplus
}
#endif
