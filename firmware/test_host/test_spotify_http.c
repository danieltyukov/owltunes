/* firmware/main/spotify_http.c against a stand-in for ESP-IDF's HTTP client (stubs/): what it sends,
 * what it hands back, and when it sends a request a second time. P8: only when the request cannot
 * have reached Spotify (a write error, or a kept-alive connection closed before any answer), never
 * after a timeout or a partial answer, so a slow "next" never skips twice. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_crt_bundle.h"
#include "esp_heap_caps.h"
#include "esp_http_client.h"
#include "spotify_http.h"
#include "unity.h"

#define MAX_PERFORMS 8
#define MAX_CHUNKS 4

typedef struct {
    esp_err_t result;
    bool status_line; /* emit HTTP_EVENT_ON_STATUS_CODE */
    int status;
    const char *retry_after; /* NULL: no Retry-After header */
    const char *chunks[MAX_CHUNKS];
    int repeat;  /* send chunks[0] this many times (long bodies) */
    bool closes; /* the client closes the connection after it (an answer with Connection: close) */
} scripted_t;

struct esp_http_client {
    esp_http_client_config_t config;
    int status;
    bool connected; /* like esp_http_client, it opens a connection when it holds none */
};

static struct esp_http_client s_clients[MAX_PERFORMS];
static int s_inits;
static int s_cleanups;
static int s_performs;
static scripted_t s_script[MAX_PERFORMS];
static int s_scripted;
static char s_url[512];
static esp_http_client_method_t s_method;
static char s_authorization[600]; /* "" when the client holds no Authorization header */
static char s_auth_at_perform[600];
static char s_content_type[64];
static char s_post[2048];
static char s_logged[2048];

const char *esp_err_to_name(esp_err_t code)
{
    return code == ESP_OK ? "ESP_OK" : "ESP_FAIL";
}

esp_err_t esp_crt_bundle_attach(void *conf)
{
    (void)conf;
    return ESP_OK;
}

void *heap_caps_malloc(size_t size, uint32_t caps)
{
    (void)caps;
    return malloc(size);
}

void stub_log(char level, const char *tag, const char *fmt, ...)
{
    (void)level;
    (void)tag;
    char line[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(line, sizeof line, fmt, args);
    va_end(args);
    strncat(s_logged, line, sizeof s_logged - strlen(s_logged) - 1);
}

esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t *config)
{
    TEST_ASSERT_TRUE(s_inits < MAX_PERFORMS);
    esp_http_client_handle_t c = &s_clients[s_inits++];
    c->config = *config;
    c->status = -1;
    c->connected = false;
    s_authorization[0] = '\0';
    s_content_type[0] = '\0';
    return c;
}

esp_err_t esp_http_client_cleanup(esp_http_client_handle_t client)
{
    (void)client;
    s_cleanups++;
    return ESP_OK;
}

esp_err_t esp_http_client_set_url(esp_http_client_handle_t client, const char *url)
{
    (void)client;
    snprintf(s_url, sizeof s_url, "%s", url);
    return ESP_OK;
}

esp_err_t esp_http_client_set_method(esp_http_client_handle_t client, esp_http_client_method_t method)
{
    (void)client;
    s_method = method;
    return ESP_OK;
}

esp_err_t esp_http_client_set_header(esp_http_client_handle_t client, const char *key, const char *value)
{
    (void)client;
    char *slot = strcmp(key, "Authorization") == 0 ? s_authorization : s_content_type;
    size_t cap = slot == s_authorization ? sizeof s_authorization : sizeof s_content_type;
    if (value == NULL && slot[0] == '\0') {
        return ESP_ERR_NOT_FOUND; /* as ESP-IDF 6.1 does when it deletes a header that is not set */
    }
    snprintf(slot, cap, "%s", value != NULL ? value : ""); /* the client keeps its own copy */
    return ESP_OK;
}

esp_err_t esp_http_client_delete_header(esp_http_client_handle_t client, const char *key)
{
    return esp_http_client_set_header(client, key, NULL);
}

esp_err_t esp_http_client_set_post_field(esp_http_client_handle_t client, const char *data, int len)
{
    snprintf(s_post, sizeof s_post, "%.*s", data != NULL ? len : 0, data != NULL ? data : "");
    if (data == NULL) {
        return esp_http_client_set_header(client, "Content-Type", NULL); /* as ESP-IDF does */
    }
    return ESP_OK;
}

static void emit(esp_http_client_handle_t client, esp_http_client_event_id_t id, const char *key,
                 const char *value, const char *data)
{
    esp_http_client_event_t evt = {
        .event_id = id,
        .client = client,
        .data = (void *)data,
        .data_len = data != NULL ? (int)strlen(data) : 0,
        .header_key = (char *)key,
        .header_value = (char *)value,
    };
    client->config.event_handler(&evt);
}

esp_err_t esp_http_client_perform(esp_http_client_handle_t client)
{
    TEST_ASSERT_TRUE(s_performs < s_scripted);
    const scripted_t *s = &s_script[s_performs++];
    snprintf(s_auth_at_perform, sizeof s_auth_at_perform, "%s", s_authorization);
    client->status = -1; /* esp_http_client_fetch_headers starts each answer at -1 */
    if (!client->connected) {
        client->connected = true;
        emit(client, HTTP_EVENT_ON_CONNECTED, NULL, NULL, NULL);
    }
    if (s->status_line) {
        client->status = s->status;
        emit(client, HTTP_EVENT_ON_STATUS_CODE, NULL, NULL, NULL);
        emit(client, HTTP_EVENT_ON_HEADER, "content-type", "application/json", NULL);
        if (s->retry_after != NULL) {
            emit(client, HTTP_EVENT_ON_HEADER, "retry-after", s->retry_after, NULL);
        }
        emit(client, HTTP_EVENT_ON_HEADERS_COMPLETE, NULL, NULL, NULL);
        if (s->status == 401 && s->result == ESP_OK) {
            /* esp_http_check_response calls esp_http_client_add_auth, which fails without Basic or
             * Digest auth (esp_http_client.c, check_response and add_auth); perform returns that
             * before it reads the body. */
            return ESP_ERR_NOT_SUPPORTED;
        }
    }
    for (int i = 0; i < MAX_CHUNKS && s->chunks[i] != NULL; i++) {
        for (int r = 0; r < (s->repeat > 0 && i == 0 ? s->repeat : 1); r++) {
            emit(client, HTTP_EVENT_ON_DATA, NULL, NULL, s->chunks[i]);
        }
    }
    if (s->closes) {
        client->connected = false;
        emit(client, HTTP_EVENT_DISCONNECTED, NULL, NULL, NULL);
    }
    return s->result;
}

int esp_http_client_get_status_code(esp_http_client_handle_t client)
{
    return client->status;
}

static void script(scripted_t s)
{
    TEST_ASSERT_TRUE(s_scripted < MAX_PERFORMS);
    s_script[s_scripted++] = s;
}

static const scripted_t OK_204 = {.result = ESP_OK, .status_line = true, .status = 204};

static void get(const char *path, spotify_request_t *req)
{
    memset(req, 0, sizeof *req);
    req->method = SPOTIFY_GET;
    snprintf(req->path, sizeof req->path, "%s", path);
}

static void post(const char *path, spotify_request_t *req)
{
    get(path, req);
    req->method = SPOTIFY_POST;
}

/* Every test starts without a connection and with nothing scripted. */
static void start(void)
{
    spotify_http_close();
    memset(s_script, 0, sizeof s_script);
    s_scripted = 0;
    s_performs = 0;
    s_inits = 0;
    s_cleanups = 0;
    s_logged[0] = '\0';
}

static void test_a_get_hands_back_status_body_and_retry_after(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    get("/v1/me/player", &req);
    script((scripted_t){.result = ESP_OK,
                        .status_line = true,
                        .status = 429,
                        .retry_after = "30",
                        .chunks = {"{\"error\":", "{\"status\":429}}"}});
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok-123", &resp));
    TEST_ASSERT_EQUAL_INT(429, resp.status);
    TEST_ASSERT_EQUAL_INT32(30, resp.retry_after_s);
    TEST_ASSERT_EQUAL_STRING("{\"error\":{\"status\":429}}", resp.body);
    TEST_ASSERT_EQUAL_size_t(strlen(resp.body), resp.len);
    TEST_ASSERT_FALSE(resp.truncated);
    TEST_ASSERT_EQUAL_STRING("https://api.spotify.com/v1/me/player", s_url);
    TEST_ASSERT_EQUAL(HTTP_METHOD_GET, s_method);
    TEST_ASSERT_EQUAL_STRING("Bearer tok-123", s_auth_at_perform);
    TEST_ASSERT_EQUAL_STRING("", s_content_type);
    TEST_ASSERT_TRUE(s_clients[0].config.disable_auto_redirect); /* the token never follows a redirect */
}

static void test_no_retry_after_header_is_minus_one(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    get("/v1/me/player", &req);
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(204, resp.status);
    TEST_ASSERT_EQUAL_INT32(-1, resp.retry_after_s);
    TEST_ASSERT_EQUAL_size_t(0, resp.len);
    TEST_ASSERT_EQUAL_STRING("", resp.body);
}

static void test_the_token_leaves_the_client_after_each_request_and_is_never_logged(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    get("/v1/me/player", &req);
    script(OK_204);
    script((scripted_t){.result = ESP_ERR_HTTP_EAGAIN});
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "secret-token", &resp));
    TEST_ASSERT_EQUAL_STRING("", s_authorization);
    TEST_ASSERT_NOT_EQUAL(ESP_OK, spotify_http_call(&req, "secret-token", &resp));
    TEST_ASSERT_EQUAL_STRING("", s_authorization);
    TEST_ASSERT_NOT_NULL(strstr(s_logged, "/v1/me/player")); /* the failure is logged ... */
    TEST_ASSERT_NULL(strstr(s_logged, "secret-token"));      /* ... without the token */
}

static void test_a_body_is_sent_as_json_and_a_later_request_without_one_drops_the_type(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    get("/v1/me/player", &req);
    req.method = SPOTIFY_PUT;
    snprintf(req.body, sizeof req.body, "{\"device_ids\":[\"abc\"]}");
    script(OK_204);
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL(HTTP_METHOD_PUT, s_method);
    TEST_ASSERT_EQUAL_STRING("application/json", s_content_type);
    TEST_ASSERT_EQUAL_STRING("{\"device_ids\":[\"abc\"]}", s_post);
    post("/v1/me/player/next", &req);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL(HTTP_METHOD_POST, s_method);
    TEST_ASSERT_EQUAL_STRING("", s_content_type);
    TEST_ASSERT_EQUAL_STRING("", s_post);
    TEST_ASSERT_EQUAL_INT(1, s_inits); /* one kept-alive connection carried both */
}

static void test_a_long_body_is_cut_and_marked(void)
{
    static spotify_request_t req;
    static char chunk[1001];
    spotify_http_response_t resp;
    memset(chunk, 'x', sizeof chunk - 1);
    get("/v1/me/player/devices", &req);
    script(
        (scripted_t){.result = ESP_OK, .status_line = true, .status = 200, .chunks = {chunk}, .repeat = 70});
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_TRUE(resp.truncated);
    TEST_ASSERT_EQUAL_size_t(SPOTIFY_HTTP_BODY_MAX - 1, resp.len);
    TEST_ASSERT_EQUAL_CHAR('\0', resp.body[resp.len]);
}

/* The first request opens the connection; the ones after it reuse it. */
static void first_request_ok(spotify_request_t *req)
{
    spotify_http_response_t resp;
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(req, "tok", &resp));
}

static void test_a_kept_alive_connection_closed_before_any_answer_is_sent_again_on_a_fresh_one(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    first_request_ok(&req);
    script((scripted_t){.result = ESP_ERR_HTTP_CONNECTION_CLOSED});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(204, resp.status);
    TEST_ASSERT_EQUAL_INT(3, s_performs);
    TEST_ASSERT_EQUAL_INT(2, s_inits); /* the second try went out on a fresh connection */
    TEST_ASSERT_EQUAL_INT(1, s_cleanups);
    TEST_ASSERT_EQUAL_STRING("Bearer tok", s_auth_at_perform);
}

static void test_a_write_error_on_a_kept_alive_connection_is_sent_again(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    first_request_ok(&req);
    script((scripted_t){.result = ESP_ERR_HTTP_WRITE_DATA});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(3, s_performs);
    TEST_ASSERT_EQUAL_INT(2, s_inits);
}

static void test_a_timeout_is_never_sent_again(void)
{
    static const esp_err_t timeouts[] = {ESP_ERR_HTTP_EAGAIN, ESP_ERR_HTTP_READ_TIMEOUT,
                                         ESP_ERR_HTTP_INCOMPLETE_DATA, ESP_ERR_HTTP_CONNECT};
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    for (size_t i = 0; i < sizeof timeouts / sizeof timeouts[0]; i++) {
        start();
        first_request_ok(&req);
        script((scripted_t){.result = timeouts[i]});
        script(OK_204); /* must not be used */
        TEST_ASSERT_EQUAL(timeouts[i], spotify_http_call(&req, "tok", &resp));
        TEST_ASSERT_EQUAL_INT(2, s_performs); /* a slow "next" is not sent twice */
        TEST_ASSERT_EQUAL_INT(1, s_cleanups); /* the next request starts on a fresh connection */
    }
}

static void test_a_connection_closed_after_part_of_the_answer_is_not_sent_again(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    first_request_ok(&req);
    script((scripted_t){.result = ESP_ERR_HTTP_CONNECTION_CLOSED, .status_line = true, .status = 200});
    script(OK_204);
    /* The status line arrived: Spotify carried "next" out. It is the answer, cut short (P32). */
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(200, resp.status);
    TEST_ASSERT_TRUE(resp.truncated);
    TEST_ASSERT_EQUAL_INT(2, s_performs);
    TEST_ASSERT_EQUAL_INT(1, s_cleanups); /* its unread rest must not reach the next request */

    start();
    first_request_ok(&req);
    script((scripted_t){.result = ESP_ERR_HTTP_CONNECTION_CLOSED, .chunks = {"{\"dev"}});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_ERR_HTTP_CONNECTION_CLOSED, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(2, s_performs);
}

static void test_a_fresh_connection_is_not_tried_twice(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    script((scripted_t){.result = ESP_ERR_HTTP_CONNECTION_CLOSED});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_ERR_HTTP_CONNECTION_CLOSED, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(1, s_performs);

    start();
    first_request_ok(&req);
    script((scripted_t){.result = ESP_ERR_HTTP_CONNECTION_CLOSED});
    script((scripted_t){.result = ESP_ERR_HTTP_CONNECTION_CLOSED});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_ERR_HTTP_CONNECTION_CLOSED, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(3, s_performs); /* at most one more try */
}

static void test_a_failed_request_leaves_no_kept_alive_connection_behind(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    first_request_ok(&req);
    script((scripted_t){.result = ESP_ERR_HTTP_READ_TIMEOUT});
    script((scripted_t){.result = ESP_ERR_HTTP_CONNECTION_CLOSED});
    script(OK_204);
    TEST_ASSERT_NOT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    /* The request after a failure opens a new connection, so a close there is a real failure. */
    TEST_ASSERT_EQUAL(ESP_ERR_HTTP_CONNECTION_CLOSED, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(3, s_performs);
    TEST_ASSERT_EQUAL_INT(2, s_inits);
}

static void test_a_401_is_an_answer_although_esp_http_client_fails_it(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    get("/v1/me/player", &req);
    first_request_ok(&req);
    script((scripted_t){.result = ESP_OK,
                        .status_line = true,
                        .status = 401,
                        .retry_after = "3",
                        .chunks = {"{\"error\":{\"status\":401}}"}});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "expired", &resp));
    TEST_ASSERT_EQUAL_INT(401, resp.status); /* so the runtime refreshes the token (P32) */
    TEST_ASSERT_EQUAL_INT32(3, resp.retry_after_s);
    TEST_ASSERT_EQUAL_size_t(0, resp.len);
    TEST_ASSERT_TRUE(resp.truncated);
    TEST_ASSERT_EQUAL_INT(2, s_performs); /* an answer is never sent again */
    TEST_ASSERT_EQUAL_INT(1, s_cleanups); /* the unread body stays on the dropped connection */
    TEST_ASSERT_EQUAL_STRING("", s_authorization);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "fresh", &resp));
    TEST_ASSERT_EQUAL_INT(204, resp.status);
    TEST_ASSERT_FALSE(resp.truncated);
    TEST_ASSERT_EQUAL_INT(2, s_inits);
}

static void test_a_fetch_header_error_on_a_kept_alive_connection_is_sent_again(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    first_request_ok(&req);
    script((scripted_t){.result = ESP_ERR_HTTP_FETCH_HEADER}); /* how TLS reports Spotify's idle close */
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(204, resp.status);
    TEST_ASSERT_EQUAL_INT(3, s_performs);
    TEST_ASSERT_EQUAL_INT(2, s_inits);
}

static void test_a_fetch_header_error_is_not_sent_again_on_a_fresh_connection_or_after_an_answer(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    script((scripted_t){.result = ESP_ERR_HTTP_FETCH_HEADER});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_ERR_HTTP_FETCH_HEADER, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(1, s_performs);

    start();
    first_request_ok(&req);
    script((scripted_t){.result = ESP_ERR_HTTP_FETCH_HEADER, .status_line = true, .status = 204});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp)); /* the partial answer */
    TEST_ASSERT_EQUAL_INT(204, resp.status);
    TEST_ASSERT_EQUAL_INT(2, s_performs);

    start();
    first_request_ok(&req);
    script((scripted_t){.result = ESP_ERR_HTTP_EAGAIN});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_ERR_HTTP_EAGAIN, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(2, s_performs);
}

static void test_a_connection_the_client_closed_is_fresh_again(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    script((scripted_t){.result = ESP_OK, .status_line = true, .status = 204, .closes = true});
    TEST_ASSERT_EQUAL(ESP_OK, spotify_http_call(&req, "tok", &resp));
    /* The next request goes out on the new connection the client opens by itself; a failure there
     * is not the stale case, so it is not sent twice (P8). */
    script((scripted_t){.result = ESP_ERR_HTTP_FETCH_HEADER});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_ERR_HTTP_FETCH_HEADER, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(2, s_performs);
    TEST_ASSERT_EQUAL_INT(1, s_inits); /* esp_http_client reconnected, the handle stayed */
}

static void test_a_connection_we_closed_is_fresh_again(void)
{
    static spotify_request_t req;
    spotify_http_response_t resp;
    post("/v1/me/player/next", &req);
    first_request_ok(&req);
    spotify_http_close(); /* as at a logout or when the network goes down */
    script((scripted_t){.result = ESP_ERR_HTTP_FETCH_HEADER});
    script(OK_204);
    TEST_ASSERT_EQUAL(ESP_ERR_HTTP_FETCH_HEADER, spotify_http_call(&req, "tok", &resp));
    TEST_ASSERT_EQUAL_INT(2, s_performs); /* the first request on the new connection is not resent */
}

#define RUN(test)                                                                                            \
    do {                                                                                                     \
        start();                                                                                             \
        RUN_TEST(test);                                                                                      \
    } while (0)

int main(void)
{
    UNITY_BEGIN();
    RUN(test_a_get_hands_back_status_body_and_retry_after);
    RUN(test_no_retry_after_header_is_minus_one);
    RUN(test_the_token_leaves_the_client_after_each_request_and_is_never_logged);
    RUN(test_a_body_is_sent_as_json_and_a_later_request_without_one_drops_the_type);
    RUN(test_a_long_body_is_cut_and_marked);
    RUN(test_a_kept_alive_connection_closed_before_any_answer_is_sent_again_on_a_fresh_one);
    RUN(test_a_write_error_on_a_kept_alive_connection_is_sent_again);
    RUN(test_a_timeout_is_never_sent_again);
    RUN(test_a_connection_closed_after_part_of_the_answer_is_not_sent_again);
    RUN(test_a_fresh_connection_is_not_tried_twice);
    RUN(test_a_failed_request_leaves_no_kept_alive_connection_behind);
    RUN(test_a_401_is_an_answer_although_esp_http_client_fails_it);
    RUN(test_a_fetch_header_error_on_a_kept_alive_connection_is_sent_again);
    RUN(test_a_fetch_header_error_is_not_sent_again_on_a_fresh_connection_or_after_an_answer);
    RUN(test_a_connection_the_client_closed_is_fresh_again);
    RUN(test_a_connection_we_closed_is_fresh_again);
    return UNITY_END();
}
