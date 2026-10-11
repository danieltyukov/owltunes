#include <string.h>

#include "spotify_gate.h"
#include "test_util.h"
#include "unity.h"

static spotify_gate_t gate;

/* Classify a real answer the way the runtime does, then record it at now_ms. */
static spotify_outcome_t answer(int status, const char *body, int32_t retry_after_s, int64_t now_ms)
{
    spotify_error_t err;
    spotify_classify_error(status, body, body ? strlen(body) : 0, retry_after_s, &err);
    return spotify_gate_record(&gate, &err, now_ms);
}

static const char QUOTA[] =
    "{\"error\":{\"status\":429,\"message\":\"Quota exceeded\",\"reason\":\"QUOTA_EXCEEDED\"}}";

static void setUpGate(void)
{
    spotify_gate_init(&gate);
}

static void test_a_new_gate_is_open(void)
{
    setUpGate();
    TEST_ASSERT_TRUE(spotify_gate_open(&gate, 0));
    TEST_ASSERT_EQUAL(OWL_LINK_API, spotify_gate_link(&gate, 0));
    TEST_ASSERT_EQUAL_INT32(0, spotify_gate_wait_s(&gate, 0));
}

static void test_success_keeps_it_open(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_OK, answer(200, "{}", -1, 1000));
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_OK, answer(204, NULL, -1, 1000));
    TEST_ASSERT_TRUE(spotify_gate_open(&gate, 1000));
}

static void test_rate_limit_waits_for_retry_after(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_WAIT, answer(429, "", 30, 1000));
    TEST_ASSERT_FALSE(spotify_gate_open(&gate, 30999));
    TEST_ASSERT_TRUE(spotify_gate_open(&gate, 31000));
    TEST_ASSERT_EQUAL_INT32(30, spotify_gate_wait_s(&gate, 1000));
    TEST_ASSERT_EQUAL_INT32(1, spotify_gate_wait_s(&gate, 30500));
    TEST_ASSERT_EQUAL(OWL_LINK_API, spotify_gate_link(&gate, 2000));
}

static void test_rate_limit_without_header_waits_five_seconds(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_WAIT, answer(429, "", -1, 0));
    TEST_ASSERT_FALSE(spotify_gate_open(&gate, 4999));
    TEST_ASSERT_TRUE(spotify_gate_open(&gate, 5000));
}

static void test_a_shorter_retry_after_never_shortens_a_block(void)
{
    setUpGate();
    answer(429, "", 60, 0);
    answer(429, "", 1, 1000);
    TEST_ASSERT_FALSE(spotify_gate_open(&gate, 59999));
}

static void test_quota_switches_to_media_keys_until_retry_after(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_WAIT, answer(429, QUOTA, 18000, 1000));
    TEST_ASSERT_TRUE(gate.quota);
    TEST_ASSERT_EQUAL(OWL_LINK_BLE, spotify_gate_link(&gate, 1000));
    TEST_ASSERT_FALSE(spotify_gate_open(&gate, 1000 + 18000 * 1000LL - 1));
    TEST_ASSERT_EQUAL(OWL_LINK_API, spotify_gate_link(&gate, 1000 + 18000 * 1000LL));
}

static void test_quota_without_retry_after_waits_at_least_a_minute_and_doubles(void)
{
    setUpGate();
    answer(429, QUOTA, -1, 0);
    TEST_ASSERT_EQUAL_INT32(60, spotify_gate_wait_s(&gate, 0));
    answer(429, QUOTA, -1, 60000);
    TEST_ASSERT_EQUAL_INT32(120, spotify_gate_wait_s(&gate, 60000));
    int64_t now = 60000;
    for (int i = 0; i < 20; i++) {
        now = gate.blocked_until_ms;
        answer(429, QUOTA, -1, now);
    }
    TEST_ASSERT_EQUAL_INT32(SPOTIFY_GATE_QUOTA_MAX_S, spotify_gate_wait_s(&gate, now));
}

static void test_a_success_after_a_lockout_resets_the_quota_backoff(void)
{
    setUpGate();
    answer(429, QUOTA, -1, 0);
    answer(429, QUOTA, -1, 60000);
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_OK, answer(200, "{}", -1, 180000));
    TEST_ASSERT_FALSE(gate.quota);
    answer(429, QUOTA, -1, 200000);
    TEST_ASSERT_EQUAL_INT32(60, spotify_gate_wait_s(&gate, 200000));
}

static void test_huge_retry_after_is_capped_at_a_day(void)
{
    setUpGate();
    answer(429, "", INT32_MAX, 0);
    TEST_ASSERT_EQUAL_INT32(SPOTIFY_GATE_RETRY_AFTER_MAX_S, spotify_gate_wait_s(&gate, 0));
}

static void test_server_errors_back_off_up_to_a_minute(void)
{
    const int32_t expected_s[] = {2, 4, 8, 16, 32, 60, 60};
    setUpGate();
    int64_t now = 0;
    for (size_t i = 0; i < sizeof expected_s / sizeof expected_s[0]; i++) {
        TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_WAIT, answer(503, "<html>busy</html>", -1, now));
        TEST_ASSERT_EQUAL_INT32(expected_s[i], spotify_gate_wait_s(&gate, now));
        now = gate.blocked_until_ms;
    }
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_OK, answer(200, "{}", -1, now));
    answer(500, "", -1, now);
    TEST_ASSERT_EQUAL_INT32(2, spotify_gate_wait_s(&gate, now));
}

static void test_no_answer_backs_off_like_a_server_error(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_WAIT, spotify_gate_record(&gate, NULL, 1000));
    TEST_ASSERT_EQUAL_INT32(2, spotify_gate_wait_s(&gate, 1000));
    spotify_error_t none = {.http_status = 0};
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_WAIT, spotify_gate_record(&gate, &none, 3000));
    TEST_ASSERT_EQUAL_INT32(4, spotify_gate_wait_s(&gate, 3000));
}

static void test_401_asks_for_a_refresh_without_blocking(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_REFRESH, answer(401, "{\"error\":{\"status\":401}}", -1, 0));
    TEST_ASSERT_TRUE(spotify_gate_open(&gate, 0));
}

static void test_client_errors_fail_without_blocking(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_FAILED,
                      answer(404, "{\"error\":{\"status\":404,\"reason\":\"NO_ACTIVE_DEVICE\"}}", -1, 0));
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_FAILED,
                      answer(403, "{\"error\":{\"status\":403,\"reason\":\"PREMIUM_REQUIRED\"}}", -1, 0));
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_FAILED, answer(400, "", -1, 0));
    TEST_ASSERT_TRUE(spotify_gate_open(&gate, 0));
}

static void test_a_token_endpoint_rate_limit_waits_for_its_retry_after(void)
{
    /* accounts.spotify.com answers a refresh with 429 and Retry-After: the same gate holds it. */
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_WAIT, answer(429, "{\"error\":\"slow_down\"}", 45, 1000));
    TEST_ASSERT_FALSE(spotify_gate_open(&gate, 45999));
    TEST_ASSERT_TRUE(spotify_gate_open(&gate, 46000));
    TEST_ASSERT_FALSE(gate.quota);
}

static void test_a_server_error_honours_a_longer_retry_after(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_WAIT, answer(503, "", 30, 0));
    TEST_ASSERT_EQUAL_INT32(30, spotify_gate_wait_s(&gate, 0));
}

static spotify_outcome_t token_answer(int status, int32_t retry_after_s, int64_t now_ms)
{
    spotify_error_t err;
    spotify_classify_error(status, "", 0, retry_after_s, &err);
    return spotify_gate_record_token(&gate, &err, now_ms);
}

static void test_an_expired_quota_lockout_does_not_stick_to_a_later_503(void)
{
    setUpGate();
    answer(429, QUOTA, 100, 0);
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_QUOTA, spotify_gate_block(&gate, 50000));
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_NONE, spotify_gate_block(&gate, 100000));
    answer(503, "", -1, 200000);
    TEST_ASSERT_EQUAL(OWL_LINK_API, spotify_gate_link(&gate, 200000));
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_BACKOFF, spotify_gate_block(&gate, 200000));
    TEST_ASSERT_FALSE(gate.quota);
}

static void test_an_expired_quota_lockout_does_not_stick_to_a_later_429_or_no_answer(void)
{
    setUpGate();
    answer(429, QUOTA, 100, 0);
    answer(429, "", 10, 200000);
    TEST_ASSERT_EQUAL(OWL_LINK_API, spotify_gate_link(&gate, 200000));
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_RATE_LIMITED, spotify_gate_block(&gate, 200000));
    setUpGate();
    answer(429, QUOTA, 100, 0);
    spotify_gate_record(&gate, NULL, 200000);
    TEST_ASSERT_EQUAL(OWL_LINK_API, spotify_gate_link(&gate, 200000));
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_BACKOFF, spotify_gate_block(&gate, 200000));
}

static void test_a_shorter_block_keeps_the_quota_kind_while_it_lasts(void)
{
    setUpGate();
    answer(429, QUOTA, 1000, 0);
    answer(503, "", -1, 1000);
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_QUOTA, spotify_gate_block(&gate, 2000));
    TEST_ASSERT_EQUAL(OWL_LINK_BLE, spotify_gate_link(&gate, 2000));
}

static void test_token_answers_do_not_reset_the_web_api_streaks(void)
{
    setUpGate();
    answer(429, QUOTA, -1, 0);
    answer(429, QUOTA, -1, 60000);
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_OK, token_answer(200, -1, 180000));
    answer(429, QUOTA, -1, 180000);
    TEST_ASSERT_EQUAL_INT32(240, spotify_gate_wait_s(&gate, 180000));

    setUpGate();
    answer(503, "", -1, 0);
    answer(503, "", -1, 2000);
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_OK, token_answer(200, -1, 6000));
    answer(503, "", -1, 6000);
    TEST_ASSERT_EQUAL_INT32(8, spotify_gate_wait_s(&gate, 6000));
}

static void test_web_api_answers_do_not_reset_the_token_streaks(void)
{
    setUpGate();
    token_answer(503, -1, 0);
    answer(200, "{}", -1, 2000);
    token_answer(503, -1, 2000);
    TEST_ASSERT_EQUAL_INT32(4, spotify_gate_wait_s(&gate, 2000));
}

static void test_other_answers_do_not_reset_the_backoff(void)
{
    setUpGate();
    answer(503, "", -1, 0);
    answer(404, "", -1, 2000);
    answer(503, "", -1, 2000);
    TEST_ASSERT_EQUAL_INT32(4, spotify_gate_wait_s(&gate, 2000));
    answer(429, "", 1, 6000);
    answer(503, "", -1, 10000);
    TEST_ASSERT_EQUAL_INT32(8, spotify_gate_wait_s(&gate, 10000));
}

static void test_a_429_without_a_wait_doubles_up_to_a_minute(void)
{
    const int32_t expected_s[] = {5, 10, 20, 40, 60, 60};
    setUpGate();
    int64_t now = 0;
    for (size_t i = 0; i < sizeof expected_s / sizeof expected_s[0]; i++) {
        answer(429, "", -1, now);
        TEST_ASSERT_EQUAL_INT32(expected_s[i], spotify_gate_wait_s(&gate, now));
        now = gate.blocked_until_ms;
    }
    answer(200, "{}", -1, now);
    answer(429, "", -1, now);
    TEST_ASSERT_EQUAL_INT32(5, spotify_gate_wait_s(&gate, now));
}

static void test_refresh_is_asked_once_per_401_streak(void)
{
    setUpGate();
    const char *body = "{\"error\":{\"status\":401}}";
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_REFRESH, answer(401, body, -1, 0));
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_FAILED, answer(401, body, -1, 0));
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_OK, token_answer(200, -1, 0));
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_REFRESH, answer(401, body, -1, 0));
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_OK, answer(200, "{}", -1, 0));
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_REFRESH, answer(401, body, -1, 0));
}

static void test_a_token_endpoint_401_is_an_invalid_client(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_OUTCOME_FAILED, token_answer(401, -1, 0));
    TEST_ASSERT_TRUE(spotify_gate_open(&gate, 0));
}

static void test_block_kinds(void)
{
    setUpGate();
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_NONE, spotify_gate_block(&gate, 0));
    answer(429, "", 3, 0);
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_RATE_LIMITED, spotify_gate_block(&gate, 0));
    TEST_ASSERT_EQUAL(SPOTIFY_BLOCK_NONE, spotify_gate_block(&gate, 3000));
}

static void test_retry_after_header_parsing(void)
{
    TEST_ASSERT_EQUAL_INT32(30, spotify_parse_retry_after("30"));
    TEST_ASSERT_EQUAL_INT32(7, spotify_parse_retry_after(" 7 "));
    TEST_ASSERT_EQUAL_INT32(0, spotify_parse_retry_after("0"));
    TEST_ASSERT_EQUAL_INT32(-1, spotify_parse_retry_after(NULL));
    TEST_ASSERT_EQUAL_INT32(-1, spotify_parse_retry_after(""));
    TEST_ASSERT_EQUAL_INT32(-1, spotify_parse_retry_after("-5"));
    TEST_ASSERT_EQUAL_INT32(-1, spotify_parse_retry_after("12s"));
    TEST_ASSERT_EQUAL_INT32(-1, spotify_parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT"));
    TEST_ASSERT_EQUAL_INT32(SPOTIFY_GATE_RETRY_AFTER_MAX_S,
                            spotify_parse_retry_after("99999999999999999999"));
}

static void test_error_names_for_the_console(void)
{
    TEST_ASSERT_EQUAL_STRING("no_active_device", spotify_error_name(SPOTIFY_ERROR_NO_ACTIVE_DEVICE));
    TEST_ASSERT_EQUAL_STRING("premium_required", spotify_error_name(SPOTIFY_ERROR_PREMIUM_REQUIRED));
    TEST_ASSERT_EQUAL_STRING("quota", spotify_error_name(SPOTIFY_ERROR_QUOTA_EXCEEDED));
    TEST_ASSERT_EQUAL_STRING("server_error", spotify_error_name(SPOTIFY_ERROR_SERVER));
    TEST_ASSERT_EQUAL_STRING("", spotify_error_name(SPOTIFY_ERROR_NONE));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_a_new_gate_is_open);
    RUN_TEST(test_success_keeps_it_open);
    RUN_TEST(test_rate_limit_waits_for_retry_after);
    RUN_TEST(test_rate_limit_without_header_waits_five_seconds);
    RUN_TEST(test_a_shorter_retry_after_never_shortens_a_block);
    RUN_TEST(test_quota_switches_to_media_keys_until_retry_after);
    RUN_TEST(test_quota_without_retry_after_waits_at_least_a_minute_and_doubles);
    RUN_TEST(test_a_success_after_a_lockout_resets_the_quota_backoff);
    RUN_TEST(test_huge_retry_after_is_capped_at_a_day);
    RUN_TEST(test_server_errors_back_off_up_to_a_minute);
    RUN_TEST(test_no_answer_backs_off_like_a_server_error);
    RUN_TEST(test_401_asks_for_a_refresh_without_blocking);
    RUN_TEST(test_client_errors_fail_without_blocking);
    RUN_TEST(test_a_token_endpoint_rate_limit_waits_for_its_retry_after);
    RUN_TEST(test_a_server_error_honours_a_longer_retry_after);
    RUN_TEST(test_an_expired_quota_lockout_does_not_stick_to_a_later_503);
    RUN_TEST(test_an_expired_quota_lockout_does_not_stick_to_a_later_429_or_no_answer);
    RUN_TEST(test_a_shorter_block_keeps_the_quota_kind_while_it_lasts);
    RUN_TEST(test_token_answers_do_not_reset_the_web_api_streaks);
    RUN_TEST(test_web_api_answers_do_not_reset_the_token_streaks);
    RUN_TEST(test_other_answers_do_not_reset_the_backoff);
    RUN_TEST(test_a_429_without_a_wait_doubles_up_to_a_minute);
    RUN_TEST(test_refresh_is_asked_once_per_401_streak);
    RUN_TEST(test_a_token_endpoint_401_is_an_invalid_client);
    RUN_TEST(test_block_kinds);
    RUN_TEST(test_retry_after_header_parsing);
    RUN_TEST(test_error_names_for_the_console);
    return UNITY_END();
}
