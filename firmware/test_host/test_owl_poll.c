#include "owl_poll.h"
#include "test_util.h"
#include "unity.h"

static owl_poll_inputs_t screen_on_playing(void)
{
    owl_poll_inputs_t in = {
        .now_ms = 10000,
        .asleep = false,
        .screen_on = true,
        .status = OWL_PLAYER_PLAYING,
        .remaining_ms = 120000,
        .last_poll_ms = 9000,
        .last_command_ms = -1,
        .blocked_until_ms = 0,
    };
    return in;
}

static void test_asleep_never_polls(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    in.asleep = true;
    TEST_ASSERT_EQUAL_INT64(OWL_POLL_NEVER, owl_poll_delay_ms(&in));
}

static void test_first_poll_is_immediate(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    in.last_poll_ms = -1;
    TEST_ASSERT_EQUAL_INT64(0, owl_poll_delay_ms(&in));
}

static void test_polls_every_four_seconds_while_playing(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    TEST_ASSERT_EQUAL_INT64(3000, owl_poll_delay_ms(&in));
}

static void test_polls_soon_after_a_command(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    in.last_command_ms = 9800;
    TEST_ASSERT_EQUAL_INT64(300, owl_poll_delay_ms(&in));
}

static void test_polls_right_after_the_track_ends(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    in.remaining_ms = 1000;
    TEST_ASSERT_EQUAL_INT64(1300, owl_poll_delay_ms(&in));
}

static void test_polls_every_fifteen_seconds_when_paused(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    in.status = OWL_PLAYER_PAUSED;
    TEST_ASSERT_EQUAL_INT64(14000, owl_poll_delay_ms(&in));
    in.status = OWL_PLAYER_NO_DEVICE;
    TEST_ASSERT_EQUAL_INT64(14000, owl_poll_delay_ms(&in));
}

static void test_standby_waits_for_track_end_but_at_least_a_minute(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    in.screen_on = false;
    in.remaining_ms = 5000;
    TEST_ASSERT_EQUAL_INT64(59000, owl_poll_delay_ms(&in));
    in.remaining_ms = 90000;
    TEST_ASSERT_EQUAL_INT64(90300, owl_poll_delay_ms(&in));
}

static void test_standby_paused_never_polls(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    in.screen_on = false;
    in.status = OWL_PLAYER_PAUSED;
    TEST_ASSERT_EQUAL_INT64(OWL_POLL_NEVER, owl_poll_delay_ms(&in));
}

static void test_rate_limit_pushes_the_poll_out(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    in.blocked_until_ms = 70000;
    TEST_ASSERT_EQUAL_INT64(60000, owl_poll_delay_ms(&in));
}

static void test_overdue_poll_is_zero_not_negative(void)
{
    owl_poll_inputs_t in = screen_on_playing();
    in.last_poll_ms = 1000;
    TEST_ASSERT_EQUAL_INT64(0, owl_poll_delay_ms(&in));
}

/* One hour with the screen on and 3.5-minute tracks must stay far below the request volume that
 * triggered Spotify's quota lockout in public reports (one poll every 3 s, all day). */
static void test_one_active_hour_stays_under_1000_polls(void)
{
    owl_player_t p;
    owl_player_init(&p);
    p.status = OWL_PLAYER_PLAYING;
    p.has_track = true;
    p.track.duration_ms = 210000;
    int64_t now = 0, last = -1;
    int polls = 0;
    while (now < 3600000) {
        owl_poll_inputs_t in = {
            .now_ms = now,
            .screen_on = true,
            .status = p.status,
            .remaining_ms = owl_player_remaining_ms(&p, now),
            .last_poll_ms = last,
            .last_command_ms = -1,
        };
        now += owl_poll_delay_ms(&in);
        polls++;
        last = now;
        if (owl_player_remaining_ms(&p, now) == 0) {
            p.progress_ms = 0; /* the next track starts */
            p.progress_at_ms = now;
        }
    }
    TEST_ASSERT_LESS_THAN_INT(1000, polls);
    TEST_ASSERT_GREATER_THAN_INT(850, polls);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_asleep_never_polls);
    RUN_TEST(test_first_poll_is_immediate);
    RUN_TEST(test_polls_every_four_seconds_while_playing);
    RUN_TEST(test_polls_soon_after_a_command);
    RUN_TEST(test_polls_right_after_the_track_ends);
    RUN_TEST(test_polls_every_fifteen_seconds_when_paused);
    RUN_TEST(test_standby_waits_for_track_end_but_at_least_a_minute);
    RUN_TEST(test_standby_paused_never_polls);
    RUN_TEST(test_rate_limit_pushes_the_poll_out);
    RUN_TEST(test_overdue_poll_is_zero_not_negative);
    RUN_TEST(test_one_active_hour_stays_under_1000_polls);
    return UNITY_END();
}
