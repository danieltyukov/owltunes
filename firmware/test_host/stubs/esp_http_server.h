/* Host stand-in for ESP-IDF's esp_http_server.h: the calls firmware/main/callback_server.c makes,
 * with the same signatures. The test scripts what httpd_start, httpd_register_uri_handler and
 * httpd_stop return. */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

typedef void *httpd_handle_t;
typedef struct httpd_req httpd_req_t;
typedef enum { HTTP_GET = 1 } httpd_method_t;

typedef struct {
    const char *uri;
    httpd_method_t method;
    esp_err_t (*handler)(httpd_req_t *r);
    void *user_ctx;
} httpd_uri_t;

typedef struct {
    uint16_t server_port;
    uint16_t max_open_sockets;
    bool lru_purge_enable;
    size_t stack_size;
} httpd_config_t;

#define HTTPD_DEFAULT_CONFIG()                                                                               \
    {                                                                                                        \
        .server_port = 80,                                                                                   \
        .max_open_sockets = 7,                                                                               \
        .lru_purge_enable = false,                                                                           \
        .stack_size = 4096,                                                                                  \
    }

#define HTTPD_200 "200 OK"
#define HTTPD_400 "400 Bad Request"

esp_err_t httpd_start(httpd_handle_t *handle, const httpd_config_t *config);
esp_err_t httpd_stop(httpd_handle_t handle);
esp_err_t httpd_register_uri_handler(httpd_handle_t handle, const httpd_uri_t *uri_handler);
size_t httpd_req_get_url_query_len(httpd_req_t *r);
esp_err_t httpd_req_get_url_query_str(httpd_req_t *r, char *buf, size_t buf_len);
esp_err_t httpd_query_key_value(const char *qry, const char *key, char *val, size_t val_size);
esp_err_t httpd_resp_set_status(httpd_req_t *r, const char *status);
esp_err_t httpd_resp_set_type(httpd_req_t *r, const char *type);
esp_err_t httpd_resp_set_hdr(httpd_req_t *r, const char *field, const char *value);
esp_err_t httpd_resp_sendstr_chunk(httpd_req_t *r, const char *str);
