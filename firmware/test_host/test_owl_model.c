#include <string.h>

#include "owl_model.h"
#include "test_util.h"
#include "unity.h"

static owl_player_t playing_at(uint32_t progress, int64_t at, uint32_t duration)
{
    owl_player_t p;
    owl_player_init(&p);
    p.status = OWL_PLAYER_PLAYING;
    p.has_track = true;
    p.track.duration_ms = duration;
    p.progress_ms = progress;
    p.progress_at_ms = at;
    return p;
}

static void test_init_is_unknown_with_unknown_volume(void)
{
    owl_player_t p;
    memset(&p, 0xAB, sizeof p);
    owl_player_init(&p);
    TEST_ASSERT_EQUAL(OWL_PLAYER_UNKNOWN, p.status);
    TEST_ASSERT_FALSE(p.has_track);
    TEST_ASSERT_FALSE(p.has_device);
    TEST_ASSERT_EQUAL_INT8(-1, p.device.volume_percent);
    TEST_ASSERT_EQUAL_STRING("", p.track.title);
    TEST_ASSERT_EQUAL(OWL_REPEAT_OFF, p.repeat);
}

static void test_progress_advances_while_playing(void)
{
    owl_player_t p = playing_at(1000, 5000, 200000);
    TEST_ASSERT_EQUAL_UINT32(4000, owl_player_progress_now(&p, 8000));
}

static void test_progress_frozen_while_paused(void)
{
    owl_player_t p = playing_at(1000, 5000, 200000);
    p.status = OWL_PLAYER_PAUSED;
    TEST_ASSERT_EQUAL_UINT32(1000, owl_player_progress_now(&p, 8000));
}

static void test_progress_clamped_to_duration(void)
{
    owl_player_t p = playing_at(9000, 0, 10000);
    TEST_ASSERT_EQUAL_UINT32(10000, owl_player_progress_now(&p, 50000));
    TEST_ASSERT_EQUAL_UINT32(0, owl_player_remaining_ms(&p, 50000));
}

static void test_clock_going_backwards_does_not_rewind(void)
{
    owl_player_t p = playing_at(1000, 5000, 200000);
    TEST_ASSERT_EQUAL_UINT32(1000, owl_player_progress_now(&p, 4000));
}

static void test_no_track_reports_zero(void)
{
    owl_player_t p;
    owl_player_init(&p);
    p.progress_ms = 1234;
    TEST_ASSERT_EQUAL_UINT32(0, owl_player_progress_now(&p, 99999));
    TEST_ASSERT_EQUAL_UINT32(0, owl_player_remaining_ms(&p, 99999));
}

static void test_remaining_is_duration_minus_progress(void)
{
    owl_player_t p = playing_at(1000, 0, 10000);
    TEST_ASSERT_EQUAL_UINT32(7000, owl_player_remaining_ms(&p, 2000));
}

static void test_list_page_init_sets_kind_and_source(void)
{
    static owl_list_page_t page;
    memset(&page, 0xCD, sizeof page);
    owl_list_page_init(&page, OWL_LIST_PLAYLIST_ITEMS, "spotify:playlist:3cEYpjA9oz9GiPac4AsH4n");
    TEST_ASSERT_EQUAL(OWL_LIST_PLAYLIST_ITEMS, page.kind);
    TEST_ASSERT_EQUAL_STRING("spotify:playlist:3cEYpjA9oz9GiPac4AsH4n", page.source_uri);
    TEST_ASSERT_EQUAL_UINT16(0, page.count);
    TEST_ASSERT_FALSE(page.has_more);
    TEST_ASSERT_EQUAL_STRING("", page.items[0].title);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_init_is_unknown_with_unknown_volume);
    RUN_TEST(test_progress_advances_while_playing);
    RUN_TEST(test_progress_frozen_while_paused);
    RUN_TEST(test_progress_clamped_to_duration);
    RUN_TEST(test_clock_going_backwards_does_not_rewind);
    RUN_TEST(test_no_track_reports_zero);
    RUN_TEST(test_remaining_is_duration_minus_progress);
    RUN_TEST(test_list_page_init_sets_kind_and_source);
    return UNITY_END();
}
