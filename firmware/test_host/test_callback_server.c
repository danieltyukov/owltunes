/* firmware/main/callback_server.c against stand-ins for ESP-IDF's HTTP server (stubs/): how it
 * keeps track of a server that will not stop. Spec 9.7: the LAN callback listens only while a login
 * is open, so a failed stop must leave the handle for another try, never forget the server. */
#include <stdarg.h>
#include <stdio.h>

#include "callback_server.h"
#include "esp_http_server.h"
#include "unity.h"

#define MAX_SCRIPTED 4

static int s_server; /* its address is the handle the stand-in hands out */
static esp_err_t s_start_result;
static esp_err_t s_register_result;
static esp_err_t s_stop_results[MAX_SCRIPTED]; /* what the next httpd_stop calls return */
static int s_stop_scripted;
static int s_starts;
static int s_stops;
static httpd_handle_t s_stopped[MAX_SCRIPTED]; /* the handle each httpd_stop call got */
static int s_errors_logged;

const char *esp_err_to_name(esp_err_t code)
{
    return code == ESP_OK ? "ESP_OK" : "ESP_FAIL";
}

void stub_log(char level, const char *tag, const char *fmt, ...)
{
    (void)tag;
    char line[160];
    va_list args;
    va_start(args, fmt);
    vsnprintf(line, sizeof line, fmt, args);
    va_end(args);
    if (level == 'E') {
        s_errors_logged++;
    }
}

esp_err_t httpd_start(httpd_handle_t *handle, const httpd_config_t *config)
{
    TEST_ASSERT_EQUAL_UINT16(80, config->server_port);
    s_starts++;
    if (s_start_result == ESP_OK) {
        *handle = &s_server;
    }
    return s_start_result;
}

esp_err_t httpd_register_uri_handler(httpd_handle_t handle, const httpd_uri_t *uri_handler)
{
    TEST_ASSERT_EQUAL_PTR(&s_server, handle);
    TEST_ASSERT_EQUAL_STRING("/callback", uri_handler->uri);
    return s_register_result;
}

esp_err_t httpd_stop(httpd_handle_t handle)
{
    TEST_ASSERT_TRUE(s_stops < MAX_SCRIPTED);
    s_stopped[s_stops] = handle;
    esp_err_t result = s_stops < s_stop_scripted ? s_stop_results[s_stops] : ESP_OK;
    s_stops++;
    return result;
}

/* The request side is not exercised here. */
size_t httpd_req_get_url_query_len(httpd_req_t *r)
{
    (void)r;
    return 0;
}

esp_err_t httpd_req_get_url_query_str(httpd_req_t *r, char *buf, size_t buf_len)
{
    (void)r;
    (void)buf;
    (void)buf_len;
    return ESP_FAIL;
}

esp_err_t httpd_query_key_value(const char *qry, const char *key, char *val, size_t val_size)
{
    (void)qry;
    (void)key;
    (void)val;
    (void)val_size;
    return ESP_ERR_NOT_FOUND;
}

esp_err_t httpd_resp_set_status(httpd_req_t *r, const char *status)
{
    (void)r;
    (void)status;
    return ESP_OK;
}

esp_err_t httpd_resp_set_type(httpd_req_t *r, const char *type)
{
    (void)r;
    (void)type;
    return ESP_OK;
}

esp_err_t httpd_resp_set_hdr(httpd_req_t *r, const char *field, const char *value)
{
    (void)r;
    (void)field;
    (void)value;
    return ESP_OK;
}

esp_err_t httpd_resp_sendstr_chunk(httpd_req_t *r, const char *str)
{
    (void)r;
    (void)str;
    return ESP_OK;
}

static const char *accept_code(const char *code, const char *state)
{
    (void)code;
    (void)state;
    return NULL;
}

/* No server left from the previous test, every call scripted to work, the counts at zero. */
static void begin(void)
{
    s_stop_scripted = 0;
    for (int i = 0; i < MAX_SCRIPTED && callback_server_running(); i++) {
        s_stops = 0;
        callback_server_stop();
    }
    TEST_ASSERT_FALSE(callback_server_running());
    s_start_result = ESP_OK;
    s_register_result = ESP_OK;
    s_starts = 0;
    s_stops = 0;
    s_errors_logged = 0;
}

static void fail_next_stop(void)
{
    s_stop_results[s_stops] = ESP_FAIL;
    s_stop_scripted = s_stops + 1;
}

static void test_start_then_stop(void)
{
    begin();
    TEST_ASSERT_EQUAL_INT(ESP_OK, callback_server_start(accept_code));
    TEST_ASSERT_TRUE(callback_server_running());
    TEST_ASSERT_EQUAL_INT(ESP_OK, callback_server_start(accept_code)); /* already listening */
    TEST_ASSERT_EQUAL_INT(1, s_starts);
    TEST_ASSERT_EQUAL_INT(ESP_OK, callback_server_stop());
    TEST_ASSERT_FALSE(callback_server_running());
    TEST_ASSERT_EQUAL_INT(1, s_stops);
    TEST_ASSERT_EQUAL_INT(0, s_errors_logged);
}

static void test_stop_without_a_server_does_nothing(void)
{
    begin();
    TEST_ASSERT_EQUAL_INT(ESP_OK, callback_server_stop());
    TEST_ASSERT_EQUAL_INT(0, s_stops);
}

static void test_a_failed_stop_keeps_the_server_and_is_retried(void)
{
    begin();
    callback_server_start(accept_code);
    fail_next_stop();
    TEST_ASSERT_EQUAL_INT(ESP_FAIL, callback_server_stop());
    TEST_ASSERT_TRUE(callback_server_running()); /* it may still be listening */
    TEST_ASSERT_EQUAL_INT(1, s_errors_logged);
    TEST_ASSERT_EQUAL_INT(ESP_OK, callback_server_stop());
    TEST_ASSERT_FALSE(callback_server_running());
    TEST_ASSERT_EQUAL_INT(2, s_stops);
    TEST_ASSERT_EQUAL_PTR(&s_server, s_stopped[0]);
    TEST_ASSERT_EQUAL_PTR(&s_server, s_stopped[1]); /* the same server, not a forgotten one */
}

static void test_a_failed_start_leaves_nothing_running(void)
{
    begin();
    s_start_result = ESP_ERR_NO_MEM;
    TEST_ASSERT_EQUAL_INT(ESP_ERR_NO_MEM, callback_server_start(accept_code));
    TEST_ASSERT_FALSE(callback_server_running());
    TEST_ASSERT_EQUAL_INT(0, s_stops);
}

static void test_a_server_without_its_route_is_stopped(void)
{
    begin();
    s_register_result = ESP_ERR_NO_MEM;
    TEST_ASSERT_EQUAL_INT(ESP_ERR_NO_MEM, callback_server_start(accept_code));
    TEST_ASSERT_FALSE(callback_server_running());
    TEST_ASSERT_EQUAL_INT(1, s_stops);
}

static void test_a_server_without_its_route_that_will_not_stop_is_kept(void)
{
    begin();
    s_register_result = ESP_ERR_NO_MEM;
    fail_next_stop();
    TEST_ASSERT_EQUAL_INT(ESP_ERR_NO_MEM, callback_server_start(accept_code));
    TEST_ASSERT_TRUE(callback_server_running()); /* the protocol task stops it when the login ends */
    TEST_ASSERT_EQUAL_INT(ESP_OK, callback_server_stop());
    TEST_ASSERT_FALSE(callback_server_running());
    TEST_ASSERT_EQUAL_PTR(s_stopped[0], s_stopped[1]);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_start_then_stop);
    RUN_TEST(test_stop_without_a_server_does_nothing);
    RUN_TEST(test_a_failed_stop_keeps_the_server_and_is_retried);
    RUN_TEST(test_a_failed_start_leaves_nothing_running);
    RUN_TEST(test_a_server_without_its_route_is_stopped);
    RUN_TEST(test_a_server_without_its_route_that_will_not_stop_is_kept);
    return UNITY_END();
}
