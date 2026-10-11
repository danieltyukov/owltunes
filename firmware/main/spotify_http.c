#include "spotify_http.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#include "esp_crt_bundle.h"
#include "esp_heap_caps.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "spotify_auth.h"
#include "spotify_gate.h"

static const char *TAG = "spotify_http";

static esp_http_client_handle_t s_client;
static bool s_used;     /* the connection carried a request before, so Spotify may have closed it */
static bool s_answered; /* the current request got at least a status line back */
static char *s_body;
static size_t s_len;
static bool s_truncated;
static int32_t s_retry_after_s;
static char s_auth[sizeof "Bearer " + SPOTIFY_ACCESS_TOKEN_LEN];

static esp_err_t on_event(esp_http_client_event_t *evt)
{
    switch (evt->event_id) {
    case HTTP_EVENT_ON_STATUS_CODE:
    case HTTP_EVENT_ON_HEADERS_COMPLETE:
        s_answered = true;
        break;
    case HTTP_EVENT_ON_HEADER:
        s_answered = true;
        if (strcasecmp(evt->header_key, "Retry-After") == 0) {
            s_retry_after_s = spotify_parse_retry_after(evt->header_value);
        }
        break;
    case HTTP_EVENT_ON_DATA:
        s_answered = true;
        if (evt->data_len > 0) {
            size_t room = SPOTIFY_HTTP_BODY_MAX - 1 - s_len;
            size_t n = (size_t)evt->data_len < room ? (size_t)evt->data_len : room;
            memcpy(s_body + s_len, evt->data, n);
            s_len += n;
            s_truncated = s_truncated || n < (size_t)evt->data_len;
        }
        break;
    default:
        break;
    }
    return ESP_OK;
}

static bool ensure_client(void)
{
    if (s_body == NULL) {
        /* PSRAM on the real boards; QEMU has none and falls back to internal RAM. */
        s_body = heap_caps_malloc(SPOTIFY_HTTP_BODY_MAX, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (s_body == NULL) {
            s_body = malloc(SPOTIFY_HTTP_BODY_MAX);
        }
    }
    if (s_body != NULL && s_client == NULL) {
        esp_http_client_config_t config = {
            .url = "https://" SPOTIFY_API_HOST "/v1/me/player",
            .timeout_ms = 10000,
            .crt_bundle_attach = esp_crt_bundle_attach,
            .event_handler = on_event,
            .buffer_size = 2048,
            .buffer_size_tx = 1536,        /* the Authorization header alone is a few hundred bytes */
            .keep_alive_enable = true,     /* TCP keep-alive probes notice a dead connection */
            .disable_auto_redirect = true, /* the access token goes to api.spotify.com only */
        };
        s_client = esp_http_client_init(&config);
        s_used = false;
    }
    return s_body != NULL && s_client != NULL;
}

static esp_http_client_method_t method_of(spotify_method_t m)
{
    switch (m) {
    case SPOTIFY_PUT:
        return HTTP_METHOD_PUT;
    case SPOTIFY_POST:
        return HTTP_METHOD_POST;
    case SPOTIFY_DELETE:
        return HTTP_METHOD_DELETE;
    case SPOTIFY_GET:
        break;
    }
    return HTTP_METHOD_GET;
}

static esp_err_t perform(const spotify_request_t *req, const char *access_token)
{
    char url[sizeof "https://" SPOTIFY_API_HOST + SPOTIFY_PATH_LEN];
    snprintf(url, sizeof url, "https://" SPOTIFY_API_HOST "%s", req->path);
    s_len = 0;
    s_truncated = false;
    s_answered = false;
    s_retry_after_s = -1;
    esp_http_client_set_url(s_client, url);
    esp_http_client_set_method(s_client, method_of(req->method));
    snprintf(s_auth, sizeof s_auth, "Bearer %s", access_token);
    esp_err_t err = esp_http_client_set_header(s_client, "Authorization", s_auth);
    memset(s_auth, 0, sizeof s_auth);
    if (err == ESP_OK && req->body[0] != '\0') {
        err = esp_http_client_set_header(s_client, "Content-Type", "application/json");
        if (err == ESP_OK) {
            err = esp_http_client_set_post_field(s_client, req->body, (int)strlen(req->body));
        }
    } else if (err == ESP_OK) {
        err = esp_http_client_set_post_field(s_client, NULL, 0); /* also drops the Content-Type */
    }
    if (err == ESP_OK) {
        err = esp_http_client_perform(s_client);
    }
    esp_http_client_delete_header(s_client, "Authorization"); /* the client's copy of the token */
    return err;
}

/* P8: only a request that cannot have reached Spotify is sent again. A write error means the request
 * never left whole; a connection closed before any answer is the kept-alive connection Spotify shut
 * while it sat idle. A timeout or a partial answer may mean Spotify carried it out. */
static bool send_again(esp_err_t err, bool reused)
{
    return reused && !s_answered && (err == ESP_ERR_HTTP_CONNECTION_CLOSED || err == ESP_ERR_HTTP_WRITE_DATA);
}

esp_err_t spotify_http_call(const spotify_request_t *req, const char *access_token,
                            spotify_http_response_t *out)
{
    memset(out, 0, sizeof *out);
    out->retry_after_s = -1;
    if (!ensure_client()) {
        return ESP_ERR_NO_MEM;
    }
    bool reused = s_used;
    esp_err_t err = perform(req, access_token);
    if (err != ESP_OK && send_again(err, reused)) {
        ESP_LOGI(TAG, "the kept-alive connection was closed; reconnecting");
        spotify_http_close();
        err = ensure_client() ? perform(req, access_token) : ESP_ERR_NO_MEM;
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "%s %s failed: %s", spotify_method_name(req->method), req->path, esp_err_to_name(err));
        spotify_http_close();
        return err;
    }
    s_used = true;
    s_body[s_len] = '\0';
    out->status = esp_http_client_get_status_code(s_client);
    out->retry_after_s = s_retry_after_s;
    out->body = s_body;
    out->len = s_len;
    out->truncated = s_truncated;
    ESP_LOGD(TAG, "%s %s: %d", spotify_method_name(req->method), req->path, out->status);
    return ESP_OK;
}

void spotify_http_close(void)
{
    if (s_client != NULL) {
        esp_http_client_cleanup(s_client);
        s_client = NULL;
    }
    s_used = false;
}
