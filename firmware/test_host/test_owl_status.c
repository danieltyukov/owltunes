#include "owl_status.h"
#include "test_util.h"
#include "unity.h"

static owl_status_inputs_t playing(void)
{
    owl_status_inputs_t in = {
        .has_networks = true,
        .online = true,
        .linked = true,
        .linking = false,
        .log_in_again = false,
        .link = OWL_LINK_API,
        .rate_limited = false,
        .player = OWL_PLAYER_PLAYING,
    };
    return in;
}

static void assert_rgb(uint8_t r, uint8_t g, uint8_t b, owl_rgb_t c)
{
    TEST_ASSERT_EQUAL_UINT8(r, c.r);
    TEST_ASSERT_EQUAL_UINT8(g, c.g);
    TEST_ASSERT_EQUAL_UINT8(b, c.b);
}

static void test_fresh_owl_needs_wifi(void)
{
    owl_status_inputs_t in = {0};
    TEST_ASSERT_EQUAL(OWL_STATUS_NEEDS_WIFI, owl_status_of(&in));
    TEST_ASSERT_EQUAL_STRING("needs_wifi", owl_status_name(owl_status_of(&in)));
}

static void test_saved_network_without_address_is_joining(void)
{
    owl_status_inputs_t in = playing();
    in.online = false;
    TEST_ASSERT_EQUAL(OWL_STATUS_JOINING, owl_status_of(&in));
}

static void test_online_without_login_needs_login(void)
{
    owl_status_inputs_t in = playing();
    in.linked = false;
    TEST_ASSERT_EQUAL(OWL_STATUS_NEEDS_LOGIN, owl_status_of(&in));
    in.log_in_again = true;
    TEST_ASSERT_EQUAL(OWL_STATUS_LOG_IN_AGAIN, owl_status_of(&in));
}

static void test_linking_wins_over_everything(void)
{
    owl_status_inputs_t in = {0};
    in.linking = true;
    TEST_ASSERT_EQUAL(OWL_STATUS_LINKING, owl_status_of(&in));
}

static void test_quota_wins_over_playback(void)
{
    owl_status_inputs_t in = playing();
    in.link = OWL_LINK_BLE;
    in.rate_limited = true;
    TEST_ASSERT_EQUAL(OWL_STATUS_QUOTA, owl_status_of(&in));
    in.link = OWL_LINK_API;
    TEST_ASSERT_EQUAL(OWL_STATUS_RATE_LIMITED, owl_status_of(&in));
}

static void test_playback_states(void)
{
    owl_status_inputs_t in = playing();
    TEST_ASSERT_EQUAL(OWL_STATUS_PLAYING, owl_status_of(&in));
    in.player = OWL_PLAYER_PAUSED;
    TEST_ASSERT_EQUAL(OWL_STATUS_PAUSED, owl_status_of(&in));
    in.player = OWL_PLAYER_NO_DEVICE;
    TEST_ASSERT_EQUAL(OWL_STATUS_NO_DEVICE, owl_status_of(&in));
    in.player = OWL_PLAYER_UNKNOWN;
    TEST_ASSERT_EQUAL(OWL_STATUS_STARTING, owl_status_of(&in));
}

static void test_steady_states_are_solid(void)
{
    assert_rgb(0, 48, 0, owl_status_led(OWL_STATUS_PLAYING, 0));
    assert_rgb(0, 48, 0, owl_status_led(OWL_STATUS_PLAYING, 1999));
    assert_rgb(0, 8, 0, owl_status_led(OWL_STATUS_PAUSED, 1500));
    assert_rgb(40, 0, 40, owl_status_led(OWL_STATUS_QUOTA, 1500));
}

static void test_waiting_for_the_person_blinks_slowly(void)
{
    assert_rgb(0, 0, 64, owl_status_led(OWL_STATUS_NEEDS_WIFI, 0));
    assert_rgb(0, 0, 64, owl_status_led(OWL_STATUS_NEEDS_WIFI, 999));
    assert_rgb(0, 0, 0, owl_status_led(OWL_STATUS_NEEDS_WIFI, 1000));
    assert_rgb(0, 0, 64, owl_status_led(OWL_STATUS_NEEDS_WIFI, 2000));
    assert_rgb(64, 20, 0, owl_status_led(OWL_STATUS_NEEDS_LOGIN, 100));
    assert_rgb(64, 0, 0, owl_status_led(OWL_STATUS_LOG_IN_AGAIN, 100));
}

static void test_waiting_for_the_network_blinks_quickly(void)
{
    assert_rgb(0, 0, 64, owl_status_led(OWL_STATUS_JOINING, 0));
    assert_rgb(0, 0, 0, owl_status_led(OWL_STATUS_JOINING, 250));
    assert_rgb(0, 0, 64, owl_status_led(OWL_STATUS_JOINING, 500));
    assert_rgb(0, 40, 40, owl_status_led(OWL_STATUS_LINKING, 10));
}

static void test_every_status_has_a_name(void)
{
    for (int s = OWL_STATUS_NEEDS_WIFI; s < OWL_STATUS_COUNT; s++) {
        TEST_ASSERT_TRUE(owl_status_name((owl_status_t)s)[0] != '\0');
    }
    TEST_ASSERT_EQUAL_STRING("rate_limited", owl_status_name(OWL_STATUS_RATE_LIMITED));
}

static void test_an_out_of_range_status_is_unknown(void)
{
    TEST_ASSERT_EQUAL_STRING("unknown", owl_status_name(OWL_STATUS_COUNT));
    TEST_ASSERT_EQUAL_STRING("unknown", owl_status_name((owl_status_t)-1));
    TEST_ASSERT_EQUAL_STRING("unknown", owl_status_name((owl_status_t)99));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_fresh_owl_needs_wifi);
    RUN_TEST(test_saved_network_without_address_is_joining);
    RUN_TEST(test_online_without_login_needs_login);
    RUN_TEST(test_linking_wins_over_everything);
    RUN_TEST(test_quota_wins_over_playback);
    RUN_TEST(test_playback_states);
    RUN_TEST(test_steady_states_are_solid);
    RUN_TEST(test_waiting_for_the_person_blinks_slowly);
    RUN_TEST(test_waiting_for_the_network_blinks_quickly);
    RUN_TEST(test_every_status_has_a_name);
    RUN_TEST(test_an_out_of_range_status_is_unknown);
    return UNITY_END();
}
