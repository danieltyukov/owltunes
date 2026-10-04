#pragma once

#include <stddef.h>
#include <stdint.h>

#include "owl_model.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { SPOTIFY_PARSE_OK, SPOTIFY_PARSE_BAD_JSON, SPOTIFY_PARSE_BAD_SHAPE } spotify_parse_result_t;

/* Parse GET /v1/me/player. An empty body (HTTP 204) means no active device. out must be an
 * initialized player: the like state and context name are kept while the track and context are
 * unchanged. On error out is left untouched. The position is stamped with the local now_ms. */
spotify_parse_result_t spotify_parse_player(const char *json, size_t len, int64_t now_ms, owl_player_t *out);

/* Parse a list response of the given kind (Task 10). my_user_id marks owned playlists browsable;
 * source_uri is stored on item lists. */
spotify_parse_result_t spotify_parse_list(owl_list_kind_t kind, const char *json, size_t len, const char *my_user_id,
                                          const char *source_uri, owl_list_page_t *out);

typedef enum {
    SPOTIFY_ERROR_NONE,
    SPOTIFY_ERROR_AUTH_EXPIRED,
    SPOTIFY_ERROR_FORBIDDEN,
    SPOTIFY_ERROR_PREMIUM_REQUIRED,
    SPOTIFY_ERROR_NOT_FOUND,
    SPOTIFY_ERROR_NO_ACTIVE_DEVICE,
    SPOTIFY_ERROR_RATE_LIMITED,
    SPOTIFY_ERROR_QUOTA_EXCEEDED,
    SPOTIFY_ERROR_SERVER,
    SPOTIFY_ERROR_OTHER,
} spotify_error_kind_t;

typedef struct {
    spotify_error_kind_t kind;
    int http_status;
    int32_t retry_after_s; /* from the Retry-After header; 5 when a 429 carries none */
    char message[128];
} spotify_error_t;

/* Classify an HTTP response. body may be empty or not JSON (proxies return HTML). */
void spotify_classify_error(int http_status, const char *body, size_t len, int32_t retry_after_s,
                            spotify_error_t *out);

#ifdef __cplusplus
}
#endif
