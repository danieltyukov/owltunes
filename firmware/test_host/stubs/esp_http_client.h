/* Host stand-in for ESP-IDF's esp_http_client.h: the calls firmware/main/spotify_http.c makes, with
 * the same signatures and error codes. The test scripts what each esp_http_client_perform sends to
 * the event handler and returns. */
#pragma once

#include <stdbool.h>

#include "esp_err.h"

#define ESP_ERR_HTTP_BASE (0x7000)
#define ESP_ERR_HTTP_CONNECT (ESP_ERR_HTTP_BASE + 2)
#define ESP_ERR_HTTP_WRITE_DATA (ESP_ERR_HTTP_BASE + 3)
#define ESP_ERR_HTTP_FETCH_HEADER (ESP_ERR_HTTP_BASE + 4)
#define ESP_ERR_HTTP_EAGAIN (ESP_ERR_HTTP_BASE + 7)
#define ESP_ERR_HTTP_CONNECTION_CLOSED (ESP_ERR_HTTP_BASE + 8)
#define ESP_ERR_HTTP_READ_TIMEOUT (ESP_ERR_HTTP_BASE + 11)
#define ESP_ERR_HTTP_INCOMPLETE_DATA (ESP_ERR_HTTP_BASE + 12)

typedef struct esp_http_client *esp_http_client_handle_t;

typedef enum {
    HTTP_EVENT_ERROR = 0,
    HTTP_EVENT_ON_CONNECTED,
    HTTP_EVENT_HEADERS_SENT,
    HTTP_EVENT_ON_HEADER,
    HTTP_EVENT_ON_HEADERS_COMPLETE,
    HTTP_EVENT_ON_STATUS_CODE,
    HTTP_EVENT_ON_DATA,
    HTTP_EVENT_ON_FINISH,
    HTTP_EVENT_DISCONNECTED,
    HTTP_EVENT_REDIRECT,
} esp_http_client_event_id_t;

typedef struct {
    esp_http_client_event_id_t event_id;
    esp_http_client_handle_t client;
    void *data;
    int data_len;
    void *user_data;
    char *header_key;
    char *header_value;
} esp_http_client_event_t;

typedef esp_err_t (*http_event_handle_cb)(esp_http_client_event_t *evt);

typedef enum {
    HTTP_METHOD_GET = 0,
    HTTP_METHOD_POST,
    HTTP_METHOD_PUT,
    HTTP_METHOD_PATCH,
    HTTP_METHOD_DELETE,
} esp_http_client_method_t;

typedef struct {
    const char *url;
    int timeout_ms;
    esp_err_t (*crt_bundle_attach)(void *conf);
    http_event_handle_cb event_handler;
    int buffer_size;
    int buffer_size_tx;
    bool keep_alive_enable;
    bool disable_auto_redirect;
} esp_http_client_config_t;

esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t *config);
esp_err_t esp_http_client_set_url(esp_http_client_handle_t client, const char *url);
esp_err_t esp_http_client_set_method(esp_http_client_handle_t client, esp_http_client_method_t method);
esp_err_t esp_http_client_set_header(esp_http_client_handle_t client, const char *key, const char *value);
esp_err_t esp_http_client_delete_header(esp_http_client_handle_t client, const char *key);
esp_err_t esp_http_client_set_post_field(esp_http_client_handle_t client, const char *data, int len);
esp_err_t esp_http_client_perform(esp_http_client_handle_t client);
int esp_http_client_get_status_code(esp_http_client_handle_t client);
esp_err_t esp_http_client_cleanup(esp_http_client_handle_t client);
