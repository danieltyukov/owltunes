#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "spotify_api.h"

/* HTTPS requests to api.spotify.com over one TLS connection that is kept open between requests.
 * Only the Spotify runtime task calls these. */

#define SPOTIFY_HTTP_BODY_MAX (64 * 1024)

typedef struct {
    int status;            /* the HTTP status */
    int32_t retry_after_s; /* the Retry-After header, -1 when there was none */
    const char *body;      /* NUL-terminated, valid until the next call */
    size_t len;
    bool truncated; /* the body was longer than SPOTIFY_HTTP_BODY_MAX - 1 bytes and was cut */
} spotify_http_response_t;

/* Send req with the access token (never logged). ESP_OK when an HTTP answer arrived, whatever its
 * status. A request is sent once more on a fresh connection only when it cannot have reached
 * Spotify: the kept-alive connection had carried a request before, and it failed while the request
 * was written or was closed before any answer arrived. Never after a timeout or a partial answer,
 * because Spotify may have carried the request out (a slow "next" must not skip twice). */
esp_err_t spotify_http_call(const spotify_request_t *req, const char *access_token,
                            spotify_http_response_t *out);

/* Drop the connection, for example when the network went down or the login changed. */
void spotify_http_close(void);
