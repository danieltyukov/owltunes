#include <string.h>

#include "owl_cmd.h"
#include "owl_cmdq.h"
#include "test_util.h"
#include "unity.h"

static owl_cmd_t cmd(owl_cmd_type_t type, int32_t value, const char *uri)
{
    owl_cmd_t c;
    owl_cmd_set(&c, type, value, uri);
    return c;
}

static owl_player_t playing(void)
{
    owl_player_t p;
    owl_player_init(&p);
    p.status = OWL_PLAYER_PLAYING;
    p.has_track = true;
    p.has_device = true;
    p.track.duration_ms = 200000;
    strcpy(p.track.uri, "spotify:track:6rqhFgbbKwnb9MLmUQDhG6");
    p.progress_ms = 10000;
    p.progress_at_ms = 1000;
    return p;
}

static void test_cmd_set_clears_previous_fields(void)
{
    owl_cmd_t c;
    memset(&c, 0x5A, sizeof c);
    owl_cmd_set(&c, OWL_CMD_LIKE, 0, "spotify:track:abc");
    TEST_ASSERT_EQUAL(OWL_CMD_LIKE, c.type);
    TEST_ASSERT_EQUAL_STRING("spotify:track:abc", c.uri);
    TEST_ASSERT_EQUAL_STRING("", c.offset_uri);
    TEST_ASSERT_EQUAL_UINT8(0, c.n_uris);
}

static void test_pause_freezes_progress_at_now(void)
{
    owl_player_t p = playing();
    owl_cmd_t c = cmd(OWL_CMD_PAUSE, 0, NULL);
    owl_player_apply_optimistic(&p, &c, 4000);
    TEST_ASSERT_EQUAL(OWL_PLAYER_PAUSED, p.status);
    TEST_ASSERT_EQUAL_UINT32(13000, owl_player_progress_now(&p, 90000));
}

static void test_play_resumes_from_frozen_position(void)
{
    owl_player_t p = playing();
    p.status = OWL_PLAYER_PAUSED;
    owl_cmd_t c = cmd(OWL_CMD_PLAY, 0, NULL);
    owl_player_apply_optimistic(&p, &c, 50000);
    TEST_ASSERT_EQUAL(OWL_PLAYER_PLAYING, p.status);
    TEST_ASSERT_EQUAL_UINT32(12000, owl_player_progress_now(&p, 52000));
}

static void test_seek_volume_like_and_skip_update_state(void)
{
    owl_player_t p = playing();
    owl_cmd_t c = cmd(OWL_CMD_SEEK, 999999, NULL);
    owl_player_apply_optimistic(&p, &c, 2000);
    TEST_ASSERT_EQUAL_UINT32(200000, p.progress_ms);
    c = cmd(OWL_CMD_VOLUME, 130, NULL);
    owl_player_apply_optimistic(&p, &c, 2000);
    TEST_ASSERT_EQUAL_INT8(100, p.device.volume_percent);
    c = cmd(OWL_CMD_LIKE, 0, "spotify:track:6rqhFgbbKwnb9MLmUQDhG6");
    owl_player_apply_optimistic(&p, &c, 2000);
    TEST_ASSERT_TRUE(p.liked);
    TEST_ASSERT_TRUE(p.liked_known);
    c = cmd(OWL_CMD_NEXT, 0, NULL);
    owl_player_apply_optimistic(&p, &c, 3000);
    TEST_ASSERT_EQUAL_UINT32(0, p.progress_ms);
}

static void test_like_for_another_track_leaves_state_alone(void)
{
    owl_player_t p = playing();
    owl_cmd_t c = cmd(OWL_CMD_LIKE, 0, "spotify:track:somethingElse");
    owl_player_apply_optimistic(&p, &c, 2000);
    TEST_ASSERT_FALSE(p.liked);
}

static void test_play_context_sets_context_and_starts(void)
{
    owl_player_t p = playing();
    p.status = OWL_PLAYER_PAUSED;
    owl_cmd_t c = cmd(OWL_CMD_PLAY_CONTEXT, 0, "spotify:playlist:3cEYpjA9oz9GiPac4AsH4n");
    owl_player_apply_optimistic(&p, &c, 2000);
    TEST_ASSERT_EQUAL_STRING("spotify:playlist:3cEYpjA9oz9GiPac4AsH4n", p.context_uri);
    TEST_ASSERT_EQUAL(OWL_PLAYER_PLAYING, p.status);
    TEST_ASSERT_EQUAL_UINT32(0, p.progress_ms);
}

static void test_queue_is_fifo(void)
{
    owl_cmdq_t q;
    owl_cmdq_init(&q);
    owl_cmd_t a = cmd(OWL_CMD_NEXT, 0, NULL), b = cmd(OWL_CMD_PREV, 0, NULL), out;
    TEST_ASSERT_TRUE(owl_cmdq_push(&q, &a));
    TEST_ASSERT_TRUE(owl_cmdq_push(&q, &b));
    TEST_ASSERT_TRUE(owl_cmdq_pop(&q, &out));
    TEST_ASSERT_EQUAL(OWL_CMD_NEXT, out.type);
    TEST_ASSERT_TRUE(owl_cmdq_pop(&q, &out));
    TEST_ASSERT_EQUAL(OWL_CMD_PREV, out.type);
    TEST_ASSERT_FALSE(owl_cmdq_pop(&q, &out));
}

static void test_volume_burst_coalesces_to_last_value(void)
{
    owl_cmdq_t q;
    owl_cmdq_init(&q);
    owl_cmd_t next = cmd(OWL_CMD_NEXT, 0, NULL), out;
    owl_cmdq_push(&q, &next);
    for (int32_t v = 0; v < 100; v++) {
        owl_cmd_t c = cmd(OWL_CMD_VOLUME, v, NULL);
        TEST_ASSERT_TRUE(owl_cmdq_push(&q, &c));
    }
    TEST_ASSERT_EQUAL_UINT8(2, owl_cmdq_count(&q));
    owl_cmdq_pop(&q, &out);
    owl_cmdq_pop(&q, &out);
    TEST_ASSERT_EQUAL(OWL_CMD_VOLUME, out.type);
    TEST_ASSERT_EQUAL_INT32(99, out.value);
}

static void test_seek_coalesces_only_when_last(void)
{
    owl_cmdq_t q;
    owl_cmdq_init(&q);
    owl_cmd_t s1 = cmd(OWL_CMD_SEEK, 1000, NULL), s2 = cmd(OWL_CMD_SEEK, 2000, NULL);
    owl_cmd_t next = cmd(OWL_CMD_NEXT, 0, NULL), s3 = cmd(OWL_CMD_SEEK, 3000, NULL);
    owl_cmdq_push(&q, &s1);
    owl_cmdq_push(&q, &s2);
    TEST_ASSERT_EQUAL_UINT8(1, owl_cmdq_count(&q));
    owl_cmdq_push(&q, &next);
    owl_cmdq_push(&q, &s3);
    TEST_ASSERT_EQUAL_UINT8(3, owl_cmdq_count(&q));
}

static void test_play_then_pause_cancel_out(void)
{
    owl_cmdq_t q;
    owl_cmdq_init(&q);
    owl_cmd_t play = cmd(OWL_CMD_PLAY, 0, NULL), pause = cmd(OWL_CMD_PAUSE, 0, NULL);
    owl_cmdq_push(&q, &play);
    owl_cmdq_push(&q, &pause);
    TEST_ASSERT_EQUAL_UINT8(0, owl_cmdq_count(&q));
}

static void test_opposite_toggle_does_not_cancel_across_other_commands(void)
{
    owl_cmdq_t q;
    owl_cmdq_init(&q);
    owl_cmd_t play = cmd(OWL_CMD_PLAY, 0, NULL), next = cmd(OWL_CMD_NEXT, 0, NULL), pause = cmd(OWL_CMD_PAUSE, 0, NULL);
    owl_cmdq_push(&q, &play);
    owl_cmdq_push(&q, &next);
    owl_cmdq_push(&q, &pause);
    TEST_ASSERT_EQUAL_UINT8(3, owl_cmdq_count(&q));
}

static void test_like_unlike_cancel_only_for_same_uri(void)
{
    owl_cmdq_t q;
    owl_cmdq_init(&q);
    owl_cmd_t like = cmd(OWL_CMD_LIKE, 0, "spotify:track:a");
    owl_cmd_t unlike_other = cmd(OWL_CMD_UNLIKE, 0, "spotify:track:b");
    owl_cmd_t unlike_b_like = cmd(OWL_CMD_LIKE, 0, "spotify:track:b");
    owl_cmdq_push(&q, &like);
    owl_cmdq_push(&q, &unlike_other);
    TEST_ASSERT_EQUAL_UINT8(2, owl_cmdq_count(&q));
    owl_cmdq_push(&q, &unlike_b_like);
    TEST_ASSERT_EQUAL_UINT8(1, owl_cmdq_count(&q));
}

static void test_full_queue_rejects_but_still_coalesces(void)
{
    owl_cmdq_t q;
    owl_cmdq_init(&q);
    owl_cmd_t vol = cmd(OWL_CMD_VOLUME, 10, NULL), next = cmd(OWL_CMD_NEXT, 0, NULL);
    owl_cmdq_push(&q, &vol);
    for (int i = 0; i < OWL_CMDQ_CAP - 1; i++) {
        TEST_ASSERT_TRUE(owl_cmdq_push(&q, &next));
    }
    TEST_ASSERT_FALSE(owl_cmdq_push(&q, &next));
    owl_cmd_t vol2 = cmd(OWL_CMD_VOLUME, 20, NULL);
    TEST_ASSERT_TRUE(owl_cmdq_push(&q, &vol2));
    TEST_ASSERT_EQUAL_UINT8(OWL_CMDQ_CAP, owl_cmdq_count(&q));
}

static void test_none_is_never_queued(void)
{
    owl_cmdq_t q;
    owl_cmdq_init(&q);
    owl_cmd_t none = cmd(OWL_CMD_NONE, 0, NULL);
    TEST_ASSERT_FALSE(owl_cmdq_push(&q, &none));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_cmd_set_clears_previous_fields);
    RUN_TEST(test_pause_freezes_progress_at_now);
    RUN_TEST(test_play_resumes_from_frozen_position);
    RUN_TEST(test_seek_volume_like_and_skip_update_state);
    RUN_TEST(test_like_for_another_track_leaves_state_alone);
    RUN_TEST(test_play_context_sets_context_and_starts);
    RUN_TEST(test_queue_is_fifo);
    RUN_TEST(test_volume_burst_coalesces_to_last_value);
    RUN_TEST(test_seek_coalesces_only_when_last);
    RUN_TEST(test_play_then_pause_cancel_out);
    RUN_TEST(test_opposite_toggle_does_not_cancel_across_other_commands);
    RUN_TEST(test_like_unlike_cancel_only_for_same_uri);
    RUN_TEST(test_full_queue_rejects_but_still_coalesces);
    RUN_TEST(test_none_is_never_queued);
    return UNITY_END();
}
