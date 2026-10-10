#include "callback_server.h"

#include <stdlib.h>
#include <string.h>

#include "esp_http_server.h"
#include "esp_log.h"
#include "spotify_auth.h"

#define QUERY_MAX 1024

static const char *TAG = "callback";
static httpd_handle_t s_server;
static callback_code_fn s_on_code;

static const char PAGE_START[] =
    "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>OwlTunes</title>"
    "<style>body{font:18px/1.5 system-ui,sans-serif;background:#000;color:#F4EDE1;margin:0 16px;"
    "display:grid;place-items:center;min-height:90vh;text-align:center}</style></head>"
    "<body><main><h1>OwlTunes</h1><p>";
static const char PAGE_END[] = "</p></main></body></html>";

/* Only fixed text goes into the page; nothing from the request is echoed back. */
static const char *message_for(const char *error)
{
    if (error == NULL) {
        return "Your owl got the login and is linking to Spotify now. You can close this tab.";
    }
    if (strcmp(error, "denied") == 0) {
        return "The Spotify login was cancelled. Start again from the setup page.";
    }
    if (strcmp(error, "expired") == 0 || strcmp(error, "no_session") == 0) {
        return "This login has expired. Start again from the setup page.";
    }
    if (strcmp(error, "busy") == 0) {
        return "Your owl is already linking. Wait a moment, then look at its screen.";
    }
    return "Your owl could not use this login. Start again from the setup page.";
}

static esp_err_t callback_get(httpd_req_t *req)
{
    const char *error = "bad_request";
    char *query = malloc(QUERY_MAX);
    char *code = malloc(SPOTIFY_CODE_LEN);
    char state[SPOTIFY_STATE_LEN];
    char denied[64];
    size_t len = httpd_req_get_url_query_len(req);
    if (query != NULL && code != NULL && len > 0 && len < QUERY_MAX &&
        httpd_req_get_url_query_str(req, query, QUERY_MAX) == ESP_OK) {
        if (httpd_query_key_value(query, "error", denied, sizeof denied) != ESP_ERR_NOT_FOUND) {
            error = "denied";
        } else if (httpd_query_key_value(query, "code", code, SPOTIFY_CODE_LEN) == ESP_OK &&
                   httpd_query_key_value(query, "state", state, sizeof state) == ESP_OK) {
            error = s_on_code(code, state);
        }
    }
    free(query);
    free(code);
    ESP_LOGI(TAG, "callback: %s", error != NULL ? error : "accepted");
    httpd_resp_set_status(req, error == NULL ? HTTPD_200 : HTTPD_400);
    httpd_resp_set_type(req, "text/html; charset=utf-8");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    httpd_resp_set_hdr(req, "Referrer-Policy", "no-referrer");
    httpd_resp_sendstr_chunk(req, PAGE_START);
    httpd_resp_sendstr_chunk(req, message_for(error));
    httpd_resp_sendstr_chunk(req, PAGE_END);
    return httpd_resp_sendstr_chunk(req, NULL);
}

esp_err_t callback_server_start(callback_code_fn on_code)
{
    if (s_server != NULL) {
        return ESP_OK;
    }
    s_on_code = on_code;
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.max_open_sockets = 3; /* leave sockets for the HTTPS client */
    config.lru_purge_enable = true;
    config.stack_size = 6144;
    const httpd_uri_t route = {.uri = "/callback", .method = HTTP_GET, .handler = callback_get};
    esp_err_t err = httpd_start(&s_server, &config);
    if (err == ESP_OK) {
        err = httpd_register_uri_handler(s_server, &route);
    }
    if (err != ESP_OK && s_server != NULL) {
        httpd_stop(s_server);
        s_server = NULL;
    }
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "listening on port 80 for the login callback");
    }
    return err;
}

void callback_server_stop(void)
{
    if (s_server != NULL) {
        httpd_stop(s_server);
        s_server = NULL;
        ESP_LOGI(TAG, "callback server stopped");
    }
}

bool callback_server_running(void)
{
    return s_server != NULL;
}
