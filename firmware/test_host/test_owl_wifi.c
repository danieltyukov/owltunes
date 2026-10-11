#include <string.h>

#include "owl_wifi.h"
#include "test_util.h"
#include "unity.h"

static owl_wifi_t w;
static owl_wifi_step_t step;

static void two_networks(void)
{
    owl_wifi_init(&w);
    step = owl_wifi_set_networks(&w, 2, -1, 0);
}

static void assert_connect(uint8_t index)
{
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_CONNECT, step.action);
    TEST_ASSERT_EQUAL_UINT8(index, step.index);
    TEST_ASSERT_EQUAL(OWL_WIFI_JOINING, w.state);
}

/* Fail every network of the current round with "not found" at now_ms. */
static void fail_round(int64_t now_ms)
{
    while (w.state == OWL_WIFI_JOINING) {
        step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, now_ms);
    }
}

static void test_no_networks_stays_idle(void)
{
    owl_wifi_init(&w);
    step = owl_wifi_set_networks(&w, 0, -1, 0);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_STOP, step.action);
    TEST_ASSERT_EQUAL(OWL_WIFI_IDLE, w.state);
    TEST_ASSERT_EQUAL_INT64(OWL_WIFI_NEVER, owl_wifi_deadline(&w));
}

static void test_first_saved_network_is_tried_first(void)
{
    two_networks();
    assert_connect(0);
    TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_NONE, step.failed);
    TEST_ASSERT_EQUAL_INT64(OWL_WIFI_ATTEMPT_MS, owl_wifi_deadline(&w));
}

static void test_missing_network_moves_on_to_the_next(void)
{
    two_networks();
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, 3000);
    assert_connect(1);
    TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_NOT_FOUND, step.failed);
    TEST_ASSERT_EQUAL_UINT8(0, step.failed_index);
    TEST_ASSERT_EQUAL_INT64(3000 + OWL_WIFI_ATTEMPT_MS, owl_wifi_deadline(&w));
}

static void test_handshake_failures_mean_a_wrong_password(void)
{
    const int reasons[] = {OWL_WIFI_REASON_AUTH_EXPIRE, OWL_WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT,
                           OWL_WIFI_REASON_AUTH_FAIL, OWL_WIFI_REASON_HANDSHAKE_TIMEOUT};
    for (size_t i = 0; i < sizeof reasons / sizeof reasons[0]; i++) {
        TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_WRONG_PASSWORD, owl_wifi_classify(reasons[i]));
    }
    TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_NOT_FOUND,
                      owl_wifi_classify(OWL_WIFI_REASON_NO_AP_FOUND_W_COMPATIBLE_SECURITY));
    TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_OTHER, owl_wifi_classify(200));
}

static void test_our_own_disconnect_is_ignored_once(void)
{
    two_networks();
    step = owl_wifi_set_networks(&w, 2, -1, 50);
    assert_connect(0);
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_ASSOC_LEAVE, 100);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, step.action);
    TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_NONE, step.failed);
    TEST_ASSERT_EQUAL(OWL_WIFI_JOINING, w.state);
    TEST_ASSERT_EQUAL_UINT8(0, w.index);
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_ASSOC_LEAVE, 200);
    assert_connect(1);
}

static void test_access_point_dropping_us_with_assoc_leave_rejoins(void)
{
    two_networks();
    step = owl_wifi_got_address(&w);
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_ASSOC_LEAVE, 9000);
    assert_connect(0);
    TEST_ASSERT_EQUAL_INT64(9000 + OWL_WIFI_ATTEMPT_MS, owl_wifi_deadline(&w));
}

static void test_leaving_online_for_a_new_list_expects_one_leave(void)
{
    two_networks();
    step = owl_wifi_got_address(&w);
    step = owl_wifi_set_networks(&w, 1, -1, 100);
    assert_connect(0);
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_ASSOC_LEAVE, 110);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, step.action);
    TEST_ASSERT_EQUAL(OWL_WIFI_JOINING, w.state);
}

static void test_timed_out_attempt_expects_one_leave(void)
{
    two_networks();
    step = owl_wifi_tick(&w, OWL_WIFI_ATTEMPT_MS);
    assert_connect(1);
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_ASSOC_LEAVE, OWL_WIFI_ATTEMPT_MS + 5);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, step.action);
    TEST_ASSERT_EQUAL_UINT8(1, w.index);
}

static void test_four_networks_are_walked_in_order_then_wait(void)
{
    owl_wifi_init(&w);
    step = owl_wifi_set_networks(&w, 4, -1, 0);
    assert_connect(0);
    for (uint8_t i = 1; i < 4; i++) {
        step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, 100 * i);
        assert_connect(i);
        TEST_ASSERT_EQUAL_UINT8(i - 1, step.failed_index);
    }
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_AUTH_FAIL, 1000);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_STOP, step.action);
    TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_WRONG_PASSWORD, step.failed);
    TEST_ASSERT_EQUAL_UINT8(3, step.failed_index);
    TEST_ASSERT_EQUAL(OWL_WIFI_WAITING, w.state);
    TEST_ASSERT_EQUAL_INT64(1000 + OWL_WIFI_BACKOFF_FIRST_MS, owl_wifi_deadline(&w));
}

static void test_one_network_goes_straight_to_waiting(void)
{
    owl_wifi_init(&w);
    step = owl_wifi_set_networks(&w, 1, -1, 0);
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, 700);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_STOP, step.action);
    TEST_ASSERT_EQUAL(OWL_WIFI_WAITING, w.state);
    TEST_ASSERT_EQUAL_INT64(700 + OWL_WIFI_BACKOFF_FIRST_MS, owl_wifi_deadline(&w));
}

static void test_list_change_while_joining_restarts_at_the_top(void)
{
    two_networks();
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, 100);
    TEST_ASSERT_EQUAL_UINT8(1, w.index);
    step = owl_wifi_set_networks(&w, 3, 1, 200);
    assert_connect(0);
    TEST_ASSERT_EQUAL_INT64(200 + OWL_WIFI_ATTEMPT_MS, owl_wifi_deadline(&w));
}

static void test_list_change_while_waiting_restarts_at_once_with_a_fresh_backoff(void)
{
    two_networks();
    fail_round(0);
    step = owl_wifi_tick(&w, owl_wifi_deadline(&w));
    fail_round(10000);
    step = owl_wifi_set_networks(&w, 2, -1, 11000);
    assert_connect(0);
    TEST_ASSERT_EQUAL_UINT8(0, w.failed_rounds);
    /* The owl is not connected, so no leave is expected: a stray one is a drop. */
    fail_round(12000);
    TEST_ASSERT_EQUAL_INT64(12000 + OWL_WIFI_BACKOFF_FIRST_MS, owl_wifi_deadline(&w));
}

static void test_keep_beyond_the_capped_list_does_not_keep_the_connection(void)
{
    owl_wifi_init(&w);
    step = owl_wifi_set_networks(&w, 9, -1, 0);
    step = owl_wifi_got_address(&w);
    step = owl_wifi_set_networks(&w, 9, 6, 100);
    assert_connect(0);
}

static void test_address_and_drop_events_while_waiting_do_nothing(void)
{
    two_networks();
    fail_round(0);
    int64_t deadline = owl_wifi_deadline(&w);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, owl_wifi_got_address(&w).action);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, 10).action);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, owl_wifi_disconnected(&w, OWL_WIFI_REASON_ASSOC_LEAVE, 20).action);
    TEST_ASSERT_EQUAL(OWL_WIFI_WAITING, w.state);
    TEST_ASSERT_EQUAL_INT64(deadline, owl_wifi_deadline(&w));
}

static void test_a_second_disconnect_after_a_failure_counts_against_the_next_network(void)
{
    two_networks();
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, 100);
    assert_connect(1);
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, 150);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_STOP, step.action);
    TEST_ASSERT_EQUAL_UINT8(1, step.failed_index);
    TEST_ASSERT_EQUAL(OWL_WIFI_WAITING, w.state);
}

static void test_failed_rounds_saturate_and_the_delay_stays_at_a_minute(void)
{
    owl_wifi_init(&w);
    step = owl_wifi_set_networks(&w, 1, -1, 0);
    int64_t now = 0;
    for (int i = 0; i < 300; i++) {
        step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, now);
        now = owl_wifi_deadline(&w);
        step = owl_wifi_tick(&w, now);
    }
    TEST_ASSERT_EQUAL_UINT8(255, w.failed_rounds);
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, now);
    TEST_ASSERT_EQUAL_UINT8(255, w.failed_rounds);
    TEST_ASSERT_EQUAL_INT64(now + OWL_WIFI_BACKOFF_MAX_MS, owl_wifi_deadline(&w));
}

static void test_attempt_without_an_address_times_out(void)
{
    two_networks();
    step = owl_wifi_tick(&w, OWL_WIFI_ATTEMPT_MS - 1);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, step.action);
    step = owl_wifi_tick(&w, OWL_WIFI_ATTEMPT_MS);
    assert_connect(1);
    TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_NO_ADDRESS, step.failed);
}

static void test_failed_round_waits_and_then_starts_again_at_the_top(void)
{
    two_networks();
    fail_round(1000);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_STOP, step.action);
    TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_NOT_FOUND, step.failed);
    TEST_ASSERT_EQUAL_UINT8(1, step.failed_index);
    TEST_ASSERT_EQUAL(OWL_WIFI_WAITING, w.state);
    TEST_ASSERT_EQUAL_INT64(1000 + OWL_WIFI_BACKOFF_FIRST_MS, owl_wifi_deadline(&w));
    step = owl_wifi_tick(&w, 1000 + OWL_WIFI_BACKOFF_FIRST_MS - 1);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, step.action);
    step = owl_wifi_tick(&w, 1000 + OWL_WIFI_BACKOFF_FIRST_MS);
    assert_connect(0);
}

static void test_backoff_doubles_up_to_a_minute(void)
{
    const int64_t expected[] = {5000, 10000, 20000, 40000, 60000, 60000};
    int64_t now = 0;
    two_networks();
    for (size_t i = 0; i < sizeof expected / sizeof expected[0]; i++) {
        fail_round(now);
        TEST_ASSERT_EQUAL_INT64(now + expected[i], owl_wifi_deadline(&w));
        now = owl_wifi_deadline(&w);
        step = owl_wifi_tick(&w, now);
        assert_connect(0);
    }
}

static void test_an_address_resets_the_backoff(void)
{
    two_networks();
    fail_round(0);
    step = owl_wifi_tick(&w, owl_wifi_deadline(&w));
    fail_round(10000);
    step = owl_wifi_tick(&w, owl_wifi_deadline(&w));
    step = owl_wifi_got_address(&w);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, step.action);
    TEST_ASSERT_EQUAL(OWL_WIFI_ONLINE, w.state);
    TEST_ASSERT_EQUAL_INT64(OWL_WIFI_NEVER, owl_wifi_deadline(&w));
    step = owl_wifi_disconnected(&w, 200, 90000);
    fail_round(90000);
    TEST_ASSERT_EQUAL_INT64(90000 + OWL_WIFI_BACKOFF_FIRST_MS, owl_wifi_deadline(&w));
}

static void test_lost_connection_rejoins_at_once_from_the_top(void)
{
    two_networks();
    step = owl_wifi_disconnected(&w, OWL_WIFI_REASON_NO_AP_FOUND, 1000);
    step = owl_wifi_got_address(&w);
    TEST_ASSERT_EQUAL_UINT8(1, w.index);
    step = owl_wifi_disconnected(&w, 200, 50000);
    assert_connect(0);
    TEST_ASSERT_EQUAL(OWL_WIFI_FAIL_NONE, step.failed);
}

static void test_a_new_list_keeps_a_working_connection(void)
{
    two_networks();
    step = owl_wifi_got_address(&w);
    step = owl_wifi_set_networks(&w, 3, 0, 5000);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, step.action);
    TEST_ASSERT_EQUAL(OWL_WIFI_ONLINE, w.state);
    TEST_ASSERT_EQUAL_UINT8(3, w.n_networks);
}

static void test_removing_the_joined_network_starts_over(void)
{
    two_networks();
    step = owl_wifi_got_address(&w);
    step = owl_wifi_set_networks(&w, 1, -1, 5000);
    assert_connect(0);
    step = owl_wifi_set_networks(&w, 0, -1, 6000);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_STOP, step.action);
    TEST_ASSERT_EQUAL(OWL_WIFI_IDLE, w.state);
}

static void test_a_list_too_long_is_capped(void)
{
    owl_wifi_init(&w);
    step = owl_wifi_set_networks(&w, 9, -1, 0);
    TEST_ASSERT_EQUAL_UINT8(OWL_WIFI_MAX_NETWORKS, w.n_networks);
}

static void test_events_in_the_wrong_state_do_nothing(void)
{
    owl_wifi_init(&w);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, owl_wifi_got_address(&w).action);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, owl_wifi_disconnected(&w, 200, 0).action);
    TEST_ASSERT_EQUAL(OWL_WIFI_DO_NOTHING, owl_wifi_tick(&w, 99999).action);
    TEST_ASSERT_EQUAL(OWL_WIFI_IDLE, w.state);
}

static void test_names_for_the_setup_page(void)
{
    TEST_ASSERT_EQUAL_STRING("wifi_not_found", owl_wifi_fail_name(OWL_WIFI_FAIL_NOT_FOUND));
    TEST_ASSERT_EQUAL_STRING("wifi_wrong_password", owl_wifi_fail_name(OWL_WIFI_FAIL_WRONG_PASSWORD));
    TEST_ASSERT_EQUAL_STRING("wifi_no_address", owl_wifi_fail_name(OWL_WIFI_FAIL_NO_ADDRESS));
    TEST_ASSERT_EQUAL_STRING("wifi_failed", owl_wifi_fail_name(OWL_WIFI_FAIL_OTHER));
    TEST_ASSERT_EQUAL_STRING("", owl_wifi_fail_name(OWL_WIFI_FAIL_NONE));
    TEST_ASSERT_EQUAL_STRING("waiting", owl_wifi_state_name(OWL_WIFI_WAITING));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_no_networks_stays_idle);
    RUN_TEST(test_first_saved_network_is_tried_first);
    RUN_TEST(test_missing_network_moves_on_to_the_next);
    RUN_TEST(test_handshake_failures_mean_a_wrong_password);
    RUN_TEST(test_our_own_disconnect_is_ignored_once);
    RUN_TEST(test_access_point_dropping_us_with_assoc_leave_rejoins);
    RUN_TEST(test_leaving_online_for_a_new_list_expects_one_leave);
    RUN_TEST(test_timed_out_attempt_expects_one_leave);
    RUN_TEST(test_four_networks_are_walked_in_order_then_wait);
    RUN_TEST(test_one_network_goes_straight_to_waiting);
    RUN_TEST(test_list_change_while_joining_restarts_at_the_top);
    RUN_TEST(test_list_change_while_waiting_restarts_at_once_with_a_fresh_backoff);
    RUN_TEST(test_keep_beyond_the_capped_list_does_not_keep_the_connection);
    RUN_TEST(test_address_and_drop_events_while_waiting_do_nothing);
    RUN_TEST(test_a_second_disconnect_after_a_failure_counts_against_the_next_network);
    RUN_TEST(test_failed_rounds_saturate_and_the_delay_stays_at_a_minute);
    RUN_TEST(test_attempt_without_an_address_times_out);
    RUN_TEST(test_failed_round_waits_and_then_starts_again_at_the_top);
    RUN_TEST(test_backoff_doubles_up_to_a_minute);
    RUN_TEST(test_an_address_resets_the_backoff);
    RUN_TEST(test_lost_connection_rejoins_at_once_from_the_top);
    RUN_TEST(test_a_new_list_keeps_a_working_connection);
    RUN_TEST(test_removing_the_joined_network_starts_over);
    RUN_TEST(test_a_list_too_long_is_capped);
    RUN_TEST(test_events_in_the_wrong_state_do_nothing);
    RUN_TEST(test_names_for_the_setup_page);
    return UNITY_END();
}
