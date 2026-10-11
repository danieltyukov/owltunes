/* firmware/main/spotify_task.c with stand-ins for FreeRTOS, the provisioning task's token service
 * and the HTTPS transport, and the real shared gate (api_gate.c): the order of requests, the 401
 * refresh, what a closed gate refuses (P18: backoff is not rate_limited), and that a request without
 * a token is neither sent nor recorded. The task loop itself is not run; the test calls its steps. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../main/spotify_task.c" /* the steps are static */
#include "test_util.h"
#include "unity.h"

#define MAX_LINES 32
#define MAX_ANSWERS 8

/* ---- stand-ins ------------------------------------------------------------------------------ */

static int64_t s_now_us;
static char s_lines[MAX_LINES][OWL_SHELL_LINE_MAX + 1];
static int s_line_count;
static provisioning_view_t s_prov;

typedef struct {
    esp_err_t err;
    int status;
    int32_t retry_after_s;
    const char *body;
} answer_t;

static answer_t s_answers[MAX_ANSWERS];
static int s_answers_scripted;
static int s_sent;
static spotify_request_t s_sent_req[MAX_ANSWERS];
static char s_sent_token[MAX_ANSWERS][32];
static int s_closes;
static const char *s_typed_during_send[4]; /* console lines that arrive while the next request runs */

static provisioning_token_t s_token_results[MAX_ANSWERS]; /* OK when not scripted */
static int s_token_scripted;
static int s_token_calls;
static bool s_token_forced[MAX_ANSWERS];

int64_t esp_timer_get_time(void)
{
    return s_now_us;
}

const char *esp_err_to_name(esp_err_t code)
{
    return code == ESP_OK ? "ESP_OK" : "ESP_FAIL";
}

void stub_log(char level, const char *tag, const char *fmt, ...)
{
    (void)level;
    (void)tag;
    (void)fmt;
}

void *heap_caps_malloc(size_t size, uint32_t caps)
{
    (void)caps;
    return malloc(size);
}

void *heap_caps_calloc(size_t n, size_t size, uint32_t caps)
{
    (void)caps;
    return calloc(n, size);
}

/* The runtime's one queue: console commands, oldest first. */
static owl_shell_cmd_t s_posted[8];
static int s_posted_head;
static int s_posted_count;

QueueHandle_t xQueueCreate(uint32_t length, uint32_t item_size)
{
    TEST_ASSERT_EQUAL_UINT32(8, length);
    TEST_ASSERT_EQUAL_UINT32(sizeof(owl_shell_cmd_t), item_size);
    return s_posted;
}

BaseType_t xQueueSend(QueueHandle_t queue, const void *item, TickType_t wait)
{
    (void)wait;
    TEST_ASSERT_EQUAL_PTR(s_posted, queue);
    if (s_posted_count == 8) {
        return pdFALSE;
    }
    memcpy(&s_posted[(s_posted_head + s_posted_count++) % 8], item, sizeof(owl_shell_cmd_t));
    return pdTRUE;
}

BaseType_t xQueueReceive(QueueHandle_t queue, void *item, TickType_t wait)
{
    (void)wait;
    TEST_ASSERT_EQUAL_PTR(s_posted, queue);
    if (s_posted_count == 0) {
        return pdFALSE;
    }
    memcpy(item, &s_posted[s_posted_head], sizeof(owl_shell_cmd_t));
    s_posted_head = (s_posted_head + 1) % 8;
    s_posted_count--;
    return pdTRUE;
}

SemaphoreHandle_t xSemaphoreCreateMutex(void)
{
    return &s_prov;
}

BaseType_t xSemaphoreTake(SemaphoreHandle_t sem, TickType_t wait)
{
    (void)sem;
    (void)wait;
    return pdTRUE;
}

BaseType_t xSemaphoreGive(SemaphoreHandle_t sem)
{
    (void)sem;
    return pdTRUE;
}

BaseType_t xTaskCreatePinnedToCore(TaskFunction_t fn, const char *name, uint32_t stack, void *arg,
                                   uint32_t priority, TaskHandle_t *handle, BaseType_t core)
{
    (void)fn;
    (void)name;
    (void)stack;
    (void)arg;
    (void)priority;
    (void)handle;
    (void)core;
    return pdPASS;
}

UBaseType_t uxTaskGetStackHighWaterMark(TaskHandle_t task)
{
    (void)task;
    return 4096;
}

void owl_console_write(const char *line)
{
    TEST_ASSERT_TRUE(s_line_count < MAX_LINES);
    snprintf(s_lines[s_line_count++], sizeof s_lines[0], "%s", line);
}

bool timesync_wait(uint32_t timeout_ms)
{
    (void)timeout_ms;
    return true;
}

void provisioning_view(provisioning_view_t *out)
{
    *out = s_prov;
}

/* The provisioning task: a fresh token "tok-<n>" per call, recorded in the gate as the real token
 * endpoint answer would be (a success re-arms the Web API's 401 refresh). */
provisioning_token_t provisioning_access_token(char *out, size_t cap, int64_t *expires_at_ms,
                                               bool force_refresh, uint32_t timeout_ms)
{
    (void)timeout_ms;
    TEST_ASSERT_TRUE(s_token_calls < MAX_ANSWERS);
    s_token_forced[s_token_calls] = force_refresh;
    provisioning_token_t result =
        s_token_calls < s_token_scripted ? s_token_results[s_token_calls] : PROVISIONING_TOKEN_OK;
    s_token_calls++;
    if (result == PROVISIONING_TOKEN_OK) {
        snprintf(out, cap, "tok-%d", s_token_calls);
        *expires_at_ms = s_now_us / 1000 + 3600 * 1000;
        spotify_error_t ok;
        spotify_classify_error(200, NULL, 0, -1, &ok);
        api_gate_record_token(&ok, s_now_us / 1000);
    }
    return result;
}

esp_err_t spotify_http_call(const spotify_request_t *req, const char *access_token,
                            spotify_http_response_t *out)
{
    TEST_ASSERT_TRUE_MESSAGE(s_sent < s_answers_scripted, "a request went out that the test did not expect");
    for (int i = 0; i < 4 && s_typed_during_send[i] != NULL; i++) {
        static owl_shell_cmd_t typed;
        owl_shell_parse(s_typed_during_send[i], &typed);
        TEST_ASSERT_TRUE(spotify_task_post(&typed)); /* what shell.c does on the console task */
        s_typed_during_send[i] = NULL;
    }
    s_sent_req[s_sent] = *req;
    snprintf(s_sent_token[s_sent], sizeof s_sent_token[0], "%s", access_token);
    const answer_t *a = &s_answers[s_sent++];
    memset(out, 0, sizeof *out);
    out->retry_after_s = a->retry_after_s;
    if (a->err != ESP_OK) {
        return a->err;
    }
    out->status = a->status;
    out->body = a->body != NULL ? a->body : "";
    out->len = strlen(out->body);
    return ESP_OK;
}

void spotify_http_close(void)
{
    s_closes++;
}

/* ---- helpers -------------------------------------------------------------------------------- */

static char *s_player_json;
static char *s_devices_json;
static char *s_quota_json;

static void answer(int status, int32_t retry_after_s, const char *body)
{
    TEST_ASSERT_TRUE(s_answers_scripted < MAX_ANSWERS);
    s_answers[s_answers_scripted++] = (answer_t){ESP_OK, status, retry_after_s, body};
}

static void no_answer(void)
{
    TEST_ASSERT_TRUE(s_answers_scripted < MAX_ANSWERS);
    s_answers[s_answers_scripted++] = (answer_t){ESP_FAIL, 0, -1, NULL};
}

static void token_result(provisioning_token_t result)
{
    s_token_results[s_token_scripted++] = result;
}

static void advance_ms(int64_t ms)
{
    s_now_us += ms * 1000;
}

/* The line that contains every one of the given fragments, or fail. */
static void expect_line(const char *a, const char *b, const char *c)
{
    for (int i = 0; i < s_line_count; i++) {
        if (strstr(s_lines[i], a) != NULL && (b == NULL || strstr(s_lines[i], b) != NULL) &&
            (c == NULL || strstr(s_lines[i], c) != NULL)) {
            return;
        }
    }
    char msg[160];
    snprintf(msg, sizeof msg, "no line with %s %s %s", a, b ? b : "", c ? c : "");
    TEST_FAIL_MESSAGE(msg);
}

static int lines_with(const char *fragment)
{
    int n = 0;
    for (int i = 0; i < s_line_count; i++) {
        n += strstr(s_lines[i], fragment) != NULL;
    }
    return n;
}

static void console(const char *text)
{
    static owl_shell_cmd_t cmd;
    owl_shell_parse(text, &cmd);
    take(&cmd, &s_prov);
}

/* An active runtime that has read a playing track on the fixture's phone, with the gate open, no
 * token yet and the console cleared. */
static void start_playing(void)
{
    if (s_buf == NULL) {
        spotify_task_start();
    }
    s_now_us += (int64_t)2 * 24 * 3600 * 1000 * 1000; /* any earlier block has run out */
    spotify_error_t ok;
    spotify_classify_error(200, NULL, 0, -1, &ok);
    api_gate_record_web(&ok, now_ms()); /* reset the Web API's streaks */
    api_gate_record_token(&ok, now_ms());
    memset(&s_prov, 0, sizeof s_prov);
    s_prov.linked = true;
    s_prov.network_up = true;
    s_active = false;
    s_line_count = 0;
    s_posted_head = 0;
    s_posted_count = 0;
    owl_player_init(&s_player);
    owl_cmdq_init(&s_buf->queue);
    forget_token();
    forget_devices();
    s_want_devices = false;
    s_want_liked = false;
    s_confirm = false;
    s_answers_scripted = 0;
    s_sent = 0;
    s_token_scripted = 0;
    s_token_calls = 0;
    s_closes = 0;
    become(true, &s_prov);
    answer(200, -1, s_player_json); /* the first poll */
    work();
    TEST_ASSERT_EQUAL(OWL_PLAYER_PLAYING, s_player.status);
    TEST_ASSERT_EQUAL_INT(1, lines_with("\"event\":\"api\",\"state\":\"ready\""));
    TEST_ASSERT_EQUAL_INT(1, lines_with("\"event\":\"player\",\"status\":\"playing\""));
    s_want_liked = false; /* the like check is tested on its own */
    forget_token();       /* the next request asks the provisioning task for "tok-1" */
    s_token_scripted = 0;
    s_token_calls = 0;
    s_line_count = 0;
    s_answers_scripted = 0;
    s_sent = 0;
    advance_ms(1000);
}

/* ---- tests ---------------------------------------------------------------------------------- */

static void test_becoming_active_polls_the_player_at_once_and_prints_it(void)
{
    start_playing();
    TEST_ASSERT_EQUAL_STRING("/v1/me/player?additional_types=episode", s_sent_req[0].path);
}

static void test_a_command_is_queued_sent_and_confirmed_by_the_poll_half_a_second_later(void)
{
    start_playing();
    console("next");
    expect_line("\"state\":\"queued\"", "\"cmd\":\"next\"", NULL);
    answer(204, -1, NULL);
    work();
    expect_line("\"state\":\"done\"", "\"cmd\":\"next\"", NULL);
    TEST_ASSERT_EQUAL(SPOTIFY_POST, s_sent_req[0].method);
    TEST_ASSERT_EQUAL_STRING("/v1/me/player/next", s_sent_req[0].path);
    TEST_ASSERT_EQUAL_STRING("tok-1", s_sent_token[0]);

    advance_ms(100);
    work(); /* the confirming poll is not due yet */
    TEST_ASSERT_EQUAL_INT(1, s_sent);
    advance_ms(OWL_POLL_AFTER_COMMAND_MS);
    answer(200, -1, s_player_json);
    work();
    TEST_ASSERT_EQUAL_INT(2, s_sent);
    TEST_ASSERT_EQUAL_STRING("/v1/me/player?additional_types=episode", s_sent_req[1].path);
    /* Printed although nothing changed: it confirms the command. */
    TEST_ASSERT_EQUAL_INT(1, lines_with("\"event\":\"player\""));
}

static void test_commands_go_one_per_pass_oldest_first(void)
{
    start_playing();
    console("pause");
    console("next");
    TEST_ASSERT_EQUAL_INT(0, s_sent);
    answer(204, -1, NULL);
    work();
    TEST_ASSERT_EQUAL_INT(1, s_sent);
    TEST_ASSERT_EQUAL_STRING("/v1/me/player/pause", s_sent_req[0].path);
    answer(204, -1, NULL);
    work();
    TEST_ASSERT_EQUAL_INT(2, s_sent);
    TEST_ASSERT_EQUAL_STRING("/v1/me/player/next", s_sent_req[1].path);
}

static void test_a_401_gets_one_forced_refresh_and_one_more_try(void)
{
    start_playing();
    console("next");
    answer(401, -1, "{\"error\":{\"status\":401,\"message\":\"The access token expired\"}}");
    answer(204, -1, NULL);
    work();
    TEST_ASSERT_EQUAL_INT(2, s_sent);
    TEST_ASSERT_EQUAL_INT(2, s_token_calls);
    TEST_ASSERT_FALSE(s_token_forced[0]);
    TEST_ASSERT_TRUE(s_token_forced[1]);
    TEST_ASSERT_EQUAL_STRING("tok-1", s_sent_token[0]);
    TEST_ASSERT_EQUAL_STRING("tok-2", s_sent_token[1]); /* the retry carries the new token */
    expect_line("\"state\":\"done\"", "\"cmd\":\"next\"", NULL);
}

static void test_a_second_401_fails_with_auth_and_is_not_tried_a_third_time(void)
{
    static const char unauthorized[] = "{\"error\":{\"status\":401,\"message\":\"Invalid access token\"}}";
    start_playing();
    console("next");
    answer(401, -1, unauthorized);
    answer(401, -1, unauthorized);
    work();
    TEST_ASSERT_EQUAL_INT(2, s_sent);
    expect_line("\"state\":\"failed\"", "\"cmd\":\"next\"", "\"error\":\"auth\"");
}

static void test_a_command_without_a_token_is_not_sent_and_not_recorded(void)
{
    start_playing();
    console("next");
    console("pause");
    token_result(PROVISIONING_TOKEN_RETRY);
    work();
    TEST_ASSERT_EQUAL_INT(0, s_sent);
    expect_line("\"state\":\"failed\"", "\"cmd\":\"next\"", "\"error\":\"network\"");
    expect_line("\"state\":\"failed\"", "\"cmd\":\"pause\"", "\"error\":\"network\""); /* dropped */
    TEST_ASSERT_TRUE(api_gate_open(now_ms())); /* no Web API answer was recorded */
    spotify_gate_t gate;
    api_gate_get(&gate);
    TEST_ASSERT_EQUAL_UINT8(0, gate.web.failures);
}

/* auth refresh, or a 401, at a closed gate: nothing is asked, and the copy Spotify may have refused
 * is not handed out afterwards either. */
static void test_a_forced_request_at_a_closed_gate_forgets_the_token(void)
{
    start_playing();
    TEST_ASSERT_EQUAL(PROVISIONING_TOKEN_OK, get_token(false));
    TEST_ASSERT_EQUAL_STRING("tok-1", s_token);
    api_gate_record_token(NULL, now_ms()); /* a lost connection: backoff */
    TEST_ASSERT_EQUAL(PROVISIONING_TOKEN_RETRY, get_token(true));
    TEST_ASSERT_EQUAL_INT(1, s_token_calls);
    advance_ms(SPOTIFY_GATE_BACKOFF_MAX_MS);
    TEST_ASSERT_EQUAL(PROVISIONING_TOKEN_OK, get_token(false));
    TEST_ASSERT_EQUAL_INT(2, s_token_calls);
    TEST_ASSERT_EQUAL_STRING("tok-2", s_token);
}

/* During an outage the gate opens between failed refreshes: without a token the api line stays on
 * backoff instead of flapping to ready, and says ready once a token is held again. */
static void test_the_api_line_waits_for_a_token_before_ready(void)
{
    start_playing();
    forget_token();
    api_gate_record_token(NULL, now_ms());
    announce(now_ms());
    TEST_ASSERT_EQUAL_INT(1, lines_with("\"event\":\"api\",\"state\":\"backoff\""));
    advance_ms(SPOTIFY_GATE_BACKOFF_MAX_MS);
    announce(now_ms());
    TEST_ASSERT_EQUAL_INT(0, lines_with("\"event\":\"api\",\"state\":\"ready\""));
    spotify_task_view_t view;
    publish();
    spotify_task_view(&view);
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_BACKOFF, view.block);
    TEST_ASSERT_EQUAL(PROVISIONING_TOKEN_OK, get_token(false));
    announce(now_ms());
    TEST_ASSERT_EQUAL_INT(1, lines_with("\"event\":\"api\",\"state\":\"ready\""));
    publish();
    spotify_task_view(&view);
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_NONE, view.block);
}

static void test_a_429_closes_the_gate_and_commands_are_refused_as_rate_limited(void)
{
    start_playing();
    console("next");
    console("pause");
    answer(429, 30, "{\"error\":{\"status\":429,\"message\":\"API rate limit exceeded\"}}");
    work();
    expect_line("\"state\":\"failed\"", "\"cmd\":\"next\"", "\"error\":\"rate_limited\"");
    expect_line("\"state\":\"failed\"", "\"cmd\":\"pause\"", "\"retry_s\":30");
    announce(now_ms());
    expect_line("\"event\":\"api\"", "\"state\":\"rate_limited\"", "\"retry_s\":30");
    console("play");
    console("devices");
    expect_line("\"cmd\":\"play\"", "\"error\":\"rate_limited\"", "\"retry_s\":30");
    expect_line("\"cmd\":\"devices\"", "\"error\":\"rate_limited\"", NULL);
    advance_ms(10 * 1000);
    work(); /* nothing goes out while the gate is closed */
    TEST_ASSERT_EQUAL_INT(1, s_sent);
    TEST_ASSERT_EQUAL_INT(0, owl_cmdq_count(&s_buf->queue));
}

static void test_a_lost_connection_is_a_backoff_not_a_rate_limit(void)
{
    start_playing();
    console("next");
    no_answer();
    work();
    expect_line("\"state\":\"failed\"", "\"cmd\":\"next\"", "\"error\":\"network\"");
    announce(now_ms());
    expect_line("\"event\":\"api\"", "\"state\":\"backoff\"", "\"retry_s\":2");
    console("pause");
    expect_line("\"cmd\":\"pause\"", "\"error\":\"backoff\"", NULL);
    TEST_ASSERT_EQUAL_INT(0, lines_with("rate_limited"));
    spotify_task_view_t view;
    publish();
    spotify_task_view(&view);
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_BACKOFF, view.block);
    advance_ms(2000);
    announce(now_ms());
    expect_line("\"event\":\"api\"", "\"state\":\"ready\"", NULL);
}

static void test_a_quota_lockout_switches_the_link_to_ble(void)
{
    start_playing();
    console("next");
    answer(429, -1, s_quota_json);
    work();
    expect_line("\"state\":\"failed\"", "\"cmd\":\"next\"", "\"error\":\"quota\"");
    spotify_task_view_t view;
    publish();
    spotify_task_view(&view);
    TEST_ASSERT_EQUAL(OWL_LINK_BLE, view.link);
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_QUOTA, view.block);
    TEST_ASSERT_TRUE(view.wait_s >= SPOTIFY_GATE_QUOTA_FIRST_S);
    console("status"); /* the state is still printed, with the link */
    expect_line("\"event\":\"player\"", "\"link\":\"ble\"", NULL);
}

static void test_devices_are_listed_and_numbered_for_transfer(void)
{
    start_playing();
    console("devices");
    answer(200, -1, s_devices_json);
    work();
    expect_line("\"event\":\"device\"", "\"n\":1", "Pixel 9");
    expect_line("\"event\":\"device\"", "\"n\":2", "Study Laptop");
    expect_line("\"event\":\"devices\"", "\"state\":\"done\"", "\"count\":3");
    TEST_ASSERT_EQUAL_STRING("/v1/me/player/devices", s_sent_req[0].path);
    console("transfer 2");
    expect_line("\"state\":\"queued\"", "\"cmd\":\"transfer\"", NULL);
    answer(204, -1, NULL);
    work();
    TEST_ASSERT_EQUAL(SPOTIFY_PUT, s_sent_req[1].method);
    TEST_ASSERT_NOT_NULL(strstr(s_sent_req[1].body, "f00dfeed0123456789abcdef0123456789abcdef"));
}

static void test_stopping_fails_waiting_commands_and_forgets_the_devices(void)
{
    start_playing();
    console("devices");
    answer(200, -1, s_devices_json);
    work();
    console("next");
    s_prov.network_up = false;
    become(false, &s_prov);
    expect_line("\"state\":\"failed\"", "\"cmd\":\"next\"", "\"error\":\"offline\"");
    expect_line("\"event\":\"api\"", "\"state\":\"stopped\"", "\"error\":\"offline\"");
    TEST_ASSERT_EQUAL_INT(1, s_closes);
    TEST_ASSERT_EQUAL(OWL_PLAYER_UNKNOWN, s_player.status);
    console("next");
    expect_line("\"state\":\"refused\"", "\"cmd\":\"next\"", "\"error\":\"offline\"");
    s_prov.network_up = true;
    become(true, &s_prov);
    s_player.status = OWL_PLAYER_NO_DEVICE;
    console("transfer 2"); /* the old numbers are gone */
    expect_line("\"state\":\"refused\"", "\"cmd\":\"transfer\"", "\"error\":\"no_such_device\"");
}

static void test_presses_made_during_a_request_merge_before_the_next_one_goes_out(void)
{
    start_playing(); /* volume 64 */
    console("next");
    s_typed_during_send[0] = "vol +5";
    s_typed_during_send[1] = "vol +5";
    s_typed_during_send[2] = "vol +5";
    answer(204, -1, NULL);
    work(); /* "next" is in flight while the three presses arrive */
    TEST_ASSERT_EQUAL_INT(3, s_posted_count);
    take_commands(&s_prov, 0); /* the next pass takes all of them first (P33) */
    TEST_ASSERT_EQUAL_INT(0, s_posted_count);
    TEST_ASSERT_EQUAL_INT(3, lines_with("\"state\":\"queued\",\"cmd\":\"volume\""));
    TEST_ASSERT_EQUAL_UINT8(1, owl_cmdq_count(&s_buf->queue)); /* merged into the newest */
    answer(204, -1, NULL);
    work();
    TEST_ASSERT_EQUAL_INT(2, s_sent);
    TEST_ASSERT_EQUAL_STRING("/v1/me/player/volume?volume_percent=79", s_sent_req[1].path);
    advance_ms(OWL_POLL_AFTER_COMMAND_MS + 100);
    answer(200, -1, s_player_json);
    work(); /* then the confirming poll, not another volume step */
    TEST_ASSERT_EQUAL_STRING("/v1/me/player?additional_types=episode", s_sent_req[2].path);

    start_playing();
    console("next");
    s_typed_during_send[0] = "pause";
    s_typed_during_send[1] = "play";
    answer(204, -1, NULL);
    work();
    take_commands(&s_prov, 0);
    TEST_ASSERT_EQUAL_UINT8(0, owl_cmdq_count(&s_buf->queue)); /* play undid pause: nothing to send */
}

int main(void)
{
    size_t len;
    s_player_json = read_fixture("player_track.json", &len);
    char *no_volume = strstr(s_player_json, "\"supports_volume\": false");
    TEST_ASSERT_NOT_NULL(no_volume); /* this test's phone allows volume changes */
    memcpy(no_volume, "\"supports_volume\":  true", strlen("\"supports_volume\": false"));
    s_devices_json = read_fixture("devices.json", &len);
    s_quota_json = read_fixture("error_quota.json", &len);
    UNITY_BEGIN();
    RUN_TEST(test_becoming_active_polls_the_player_at_once_and_prints_it);
    RUN_TEST(test_a_command_is_queued_sent_and_confirmed_by_the_poll_half_a_second_later);
    RUN_TEST(test_commands_go_one_per_pass_oldest_first);
    RUN_TEST(test_a_401_gets_one_forced_refresh_and_one_more_try);
    RUN_TEST(test_a_second_401_fails_with_auth_and_is_not_tried_a_third_time);
    RUN_TEST(test_a_command_without_a_token_is_not_sent_and_not_recorded);
    RUN_TEST(test_a_forced_request_at_a_closed_gate_forgets_the_token);
    RUN_TEST(test_the_api_line_waits_for_a_token_before_ready);
    RUN_TEST(test_a_429_closes_the_gate_and_commands_are_refused_as_rate_limited);
    RUN_TEST(test_a_lost_connection_is_a_backoff_not_a_rate_limit);
    RUN_TEST(test_a_quota_lockout_switches_the_link_to_ble);
    RUN_TEST(test_devices_are_listed_and_numbered_for_transfer);
    RUN_TEST(test_stopping_fails_waiting_commands_and_forgets_the_devices);
    RUN_TEST(test_presses_made_during_a_request_merge_before_the_next_one_goes_out);
    int failures = UNITY_END();
    free(s_player_json);
    free(s_devices_json);
    free(s_quota_json);
    return failures;
}
