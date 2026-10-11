#include "spotify_link.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#include "api_gate.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "owl_text.h"
#include "spotify_gate.h"
#include "spotify_parse.h"

#define REQUEST_MAX 1024
#define RESPONSE_MAX 4096

static const char *TAG = "spotify_link";

typedef struct {
    char *data;
    size_t len;
    bool overflow;
    int32_t retry_after_s; /* the Retry-After header, -1 when there was none */
} response_t;

static esp_err_t on_http_event(esp_http_client_event_t *evt)
{
    response_t *r = evt->user_data;
    if (evt->event_id == HTTP_EVENT_ON_HEADER && strcasecmp(evt->header_key, "Retry-After") == 0) {
        r->retry_after_s = spotify_parse_retry_after(evt->header_value);
    } else if (evt->event_id == HTTP_EVENT_ON_DATA) {
        if (r->len + (size_t)evt->data_len < RESPONSE_MAX) {
            memcpy(r->data + r->len, evt->data, (size_t)evt->data_len);
            r->len += (size_t)evt->data_len;
        } else {
            r->overflow = true;
        }
    }
    return ESP_OK;
}

/* What the token endpoint answered, for the shared gate: its status and Retry-After decide when the
 * next token request may go out (P15: Retry-After is honoured here as on the Web API). The body is
 * not read; err is ESP_OK only when an HTTP answer arrived. */
static void record_answer(esp_err_t err, int status, int32_t retry_after_s)
{
    int64_t now_ms = esp_timer_get_time() / 1000;
    if (err != ESP_OK) {
        api_gate_record_token(NULL, now_ms);
        return;
    }
    spotify_error_t answer;
    spotify_classify_error(status, NULL, 0, retry_after_s, &answer);
    api_gate_record_token(&answer, now_ms);
}

/* POST a form body to the token endpoint and parse the answer. Tokens are never logged. */
static spotify_token_result_t post_token(const char *body, int64_t now_ms, spotify_token_t *token,
                                         char *error, size_t error_cap)
{
    response_t response = {.data = malloc(RESPONSE_MAX), .retry_after_s = -1};
    esp_http_client_config_t config = {
        .url = "https://" SPOTIFY_ACCOUNTS_HOST SPOTIFY_TOKEN_PATH,
        .method = HTTP_METHOD_POST,
        .timeout_ms = 15000,
        .crt_bundle_attach = esp_crt_bundle_attach,
        .event_handler = on_http_event,
        .user_data = &response,
    };
    esp_http_client_handle_t client = response.data ? esp_http_client_init(&config) : NULL;
    if (client == NULL) {
        free(response.data);
        owl_utf8_copy(error, error_cap, "no_memory");
        record_answer(ESP_ERR_NO_MEM, 0, -1); /* back off like a lost connection, not every second */
        return SPOTIFY_TOKEN_RETRY;
    }
    esp_http_client_set_header(client, "Content-Type", "application/x-www-form-urlencoded");
    esp_http_client_set_post_field(client, body, (int)strlen(body));
    esp_err_t err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);
    record_answer(err, status, response.retry_after_s);

    spotify_token_result_t result;
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "token request failed: %s", esp_err_to_name(err));
        owl_utf8_copy(error, error_cap, "network");
        result = SPOTIFY_TOKEN_RETRY;
    } else if (response.overflow) {
        owl_utf8_copy(error, error_cap, "too_long");
        result = SPOTIFY_TOKEN_BAD_RESPONSE;
    } else {
        result = spotify_parse_token_response(status, response.data, response.len, now_ms, token, error,
                                              error_cap);
        if (result != SPOTIFY_TOKEN_OK && error[0] == '\0') {
            /* No error code from Spotify (429, 5xx, unreadable answer): say what the status was. */
            if (status > 0) {
                snprintf(error, error_cap, "http_%d", status);
            } else {
                owl_utf8_copy(error, error_cap, "network");
            }
        }
        ESP_LOGI(TAG, "token endpoint answered %d %s", status, error[0] != '\0' ? error : "ok");
    }
    memset(response.data, 0, RESPONSE_MAX); /* it held tokens */
    free(response.data);
    return result;
}

static spotify_token_result_t post_body(char *body, bool built, int64_t now_ms, spotify_token_t *token,
                                        char *error, size_t error_cap)
{
    spotify_token_result_t result = SPOTIFY_TOKEN_BAD_RESPONSE;
    owl_utf8_copy(error, error_cap, "bad_request");
    if (built) {
        result = post_token(body, now_ms, token, error, error_cap);
    }
    if (body != NULL) {
        memset(body, 0, REQUEST_MAX);
        free(body);
    }
    return result;
}

spotify_token_result_t spotify_link_exchange(const owl_settings_t *s, const char *code, const char *verifier,
                                             int64_t now_ms, spotify_token_t *token, char *error,
                                             size_t error_cap)
{
    char *body = malloc(REQUEST_MAX);
    bool built = body != NULL && spotify_token_body_for_code(s->client_id, s->redirect_uri, code, verifier,
                                                             body, REQUEST_MAX);
    return post_body(body, built, now_ms, token, error, error_cap);
}

spotify_token_result_t spotify_link_refresh(const owl_settings_t *s, int64_t now_ms, spotify_token_t *token,
                                            char *error, size_t error_cap)
{
    char *body = malloc(REQUEST_MAX);
    bool built =
        body != NULL && spotify_token_body_for_refresh(s->client_id, token->refresh_token, body, REQUEST_MAX);
    return post_body(body, built, now_ms, token, error, error_cap);
}
