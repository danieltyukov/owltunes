#include <stdlib.h>
#include <string.h>

#include "spotify_parse.h"
#include "test_util.h"
#include "unity.h"

#define NOW 777000

static owl_player_t player;

static spotify_parse_result_t parse_fixture(const char *name)
{
    size_t len;
    char *json = read_fixture(name, &len);
    spotify_parse_result_t r = spotify_parse_player(json, len, NOW, &player);
    free(json);
    return r;
}

static void test_track_is_parsed(void)
{
    owl_player_init(&player);
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse_fixture("player_track.json"));
    TEST_ASSERT_EQUAL(OWL_PLAYER_PLAYING, player.status);
    TEST_ASSERT_TRUE(player.has_track);
    TEST_ASSERT_EQUAL(OWL_ITEM_TRACK, player.track.kind);
    TEST_ASSERT_EQUAL_STRING("Night Flight", player.track.title);
    TEST_ASSERT_EQUAL_STRING("The Barn Owls, Luna Feathers", player.track.subtitle);
    TEST_ASSERT_EQUAL_STRING("Moonlit Barn", player.track.album);
    TEST_ASSERT_EQUAL_STRING("https://i.scdn.co/image/ab67616d00001e02moonlitbarn300", player.track.art_url);
    TEST_ASSERT_EQUAL_STRING("spotify:track:6rqhFgbbKwnb9MLmUQDhG6", player.track.uri);
    TEST_ASSERT_EQUAL_UINT32(215000, player.track.duration_ms);
    TEST_ASSERT_EQUAL_UINT32(83000, player.progress_ms);
    TEST_ASSERT_EQUAL_INT64(NOW, player.progress_at_ms);
    TEST_ASSERT_TRUE(player.shuffle);
    TEST_ASSERT_EQUAL(OWL_REPEAT_CONTEXT, player.repeat);
    TEST_ASSERT_EQUAL_STRING("spotify:playlist:3cEYpjA9oz9GiPac4AsH4n", player.context_uri);
    TEST_ASSERT_TRUE(player.has_device);
    TEST_ASSERT_EQUAL_STRING("Pixel 9", player.device.name);
    TEST_ASSERT_EQUAL_STRING("Smartphone", player.device.type);
    TEST_ASSERT_FALSE(player.device.supports_volume);
    TEST_ASSERT_EQUAL_INT8(64, player.device.volume_percent);
}

static void test_empty_body_means_no_device(void)
{
    owl_player_init(&player);
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, spotify_parse_player("", 0, NOW, &player));
    TEST_ASSERT_EQUAL(OWL_PLAYER_NO_DEVICE, player.status);
    TEST_ASSERT_FALSE(player.has_track);
}

static void test_ad_has_no_track_and_null_volume(void)
{
    owl_player_init(&player);
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse_fixture("player_ad.json"));
    TEST_ASSERT_FALSE(player.has_track);
    TEST_ASSERT_EQUAL(OWL_ITEM_AD, player.track.kind);
    TEST_ASSERT_EQUAL(OWL_PLAYER_PLAYING, player.status);
    TEST_ASSERT_EQUAL_INT8(-1, player.device.volume_percent);
    TEST_ASSERT_EQUAL_STRING("", player.context_uri);
}

static void test_episode_uses_show_and_episode_art(void)
{
    owl_player_init(&player);
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse_fixture("player_episode.json"));
    TEST_ASSERT_EQUAL(OWL_ITEM_EPISODE, player.track.kind);
    TEST_ASSERT_EQUAL_STRING("Owls After Dark", player.track.title);
    TEST_ASSERT_EQUAL_STRING("Night Birds Podcast", player.track.subtitle);
    TEST_ASSERT_EQUAL_STRING("https://i.scdn.co/image/episode300", player.track.art_url);
}

static void test_unicode_title_is_truncated_safely(void)
{
    owl_player_init(&player);
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse_fixture("player_unicode_paused.json"));
    TEST_ASSERT_EQUAL(OWL_PLAYER_PAUSED, player.status);
    TEST_ASSERT_TRUE(strlen(player.track.title) < OWL_NAME_LEN);
    TEST_ASSERT_TRUE(strlen(player.track.title) > 100);
    TEST_ASSERT_TRUE(is_valid_utf8(player.track.title));
    TEST_ASSERT_EQUAL_MEMORY("\xF0\x9F\xA6\x89 ", player.track.title, 5);
    TEST_ASSERT_EQUAL_STRING("Bj\xC3\xB6rk Hoot, Caf\xC3\xA9 Owls", player.track.subtitle);
    TEST_ASSERT_EQUAL_STRING("Mitternacht \xC3\xBC" "ber dem Wald", player.track.album);
}

static void test_bad_json_leaves_player_unchanged(void)
{
    owl_player_init(&player);
    parse_fixture("player_track.json");
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_JSON, spotify_parse_player("{\"is_playing\":", 14, NOW, &player));
    TEST_ASSERT_EQUAL_STRING("Night Flight", player.track.title);
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_SHAPE, spotify_parse_player("[1,2]", 5, NOW, &player));
    TEST_ASSERT_EQUAL_STRING("Night Flight", player.track.title);
}

static void test_like_state_and_context_name_survive_a_poll(void)
{
    owl_player_init(&player);
    parse_fixture("player_track.json");
    player.liked = true;
    player.liked_known = true;
    strcpy(player.context_name, "Night Flight Mix");
    parse_fixture("player_track.json");
    TEST_ASSERT_TRUE(player.liked);
    TEST_ASSERT_TRUE(player.liked_known);
    TEST_ASSERT_EQUAL_STRING("Night Flight Mix", player.context_name);
    parse_fixture("player_episode.json");
    TEST_ASSERT_FALSE(player.liked_known);
    TEST_ASSERT_EQUAL_STRING("", player.context_name);
}

static void test_progress_past_duration_is_clamped(void)
{
    static const char json[] =
        "{\"device\":{\"id\":\"d\",\"name\":\"n\",\"type\":\"Computer\"},\"is_playing\":true,\"progress_ms\":999999,"
        "\"item\":{\"type\":\"track\",\"name\":\"x\",\"uri\":\"spotify:track:abc\",\"duration_ms\":1000}}";
    owl_player_init(&player);
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, spotify_parse_player(json, sizeof json - 1, NOW, &player));
    TEST_ASSERT_EQUAL_UINT32(1000, player.progress_ms);
    TEST_ASSERT_TRUE(player.device.supports_volume); /* missing field defaults to true */
    TEST_ASSERT_EQUAL_STRING("", player.track.art_url);
}

static void test_classify_errors(void)
{
    spotify_error_t e;
    size_t len;
    char *body;
    const char *body_text;

    spotify_classify_error(204, "", 0, 0, &e);
    TEST_ASSERT_EQUAL(SPOTIFY_ERROR_NONE, e.kind);

    body_text = "{\"error\":{\"status\":401,\"message\":\"The access token expired\"}}";
    spotify_classify_error(401, body_text, strlen(body_text), 0, &e);
    TEST_ASSERT_EQUAL(SPOTIFY_ERROR_AUTH_EXPIRED, e.kind);
    TEST_ASSERT_EQUAL_STRING("The access token expired", e.message);

    body = read_fixture("error_quota.json", &len);
    spotify_classify_error(429, body, len, 17197, &e);
    free(body);
    TEST_ASSERT_EQUAL(SPOTIFY_ERROR_QUOTA_EXCEEDED, e.kind);
    TEST_ASSERT_EQUAL_INT32(17197, e.retry_after_s);

    spotify_classify_error(429, "", 0, 0, &e);
    TEST_ASSERT_EQUAL(SPOTIFY_ERROR_RATE_LIMITED, e.kind);
    TEST_ASSERT_EQUAL_INT32(5, e.retry_after_s);

    body = read_fixture("error_no_active_device.json", &len);
    spotify_classify_error(404, body, len, 0, &e);
    free(body);
    TEST_ASSERT_EQUAL(SPOTIFY_ERROR_NO_ACTIVE_DEVICE, e.kind);

    body_text = "{\"error\":{\"status\":404,\"message\":\"Not found.\"}}";
    spotify_classify_error(404, body_text, strlen(body_text), 0, &e);
    TEST_ASSERT_EQUAL(SPOTIFY_ERROR_NOT_FOUND, e.kind);

    body = read_fixture("error_premium.json", &len);
    spotify_classify_error(403, body, len, 0, &e);
    free(body);
    TEST_ASSERT_EQUAL(SPOTIFY_ERROR_PREMIUM_REQUIRED, e.kind);

    spotify_classify_error(502, "<html>Bad gateway</html>", 24, 0, &e);
    TEST_ASSERT_EQUAL(SPOTIFY_ERROR_SERVER, e.kind);
    TEST_ASSERT_EQUAL_INT(502, e.http_status);

    spotify_classify_error(400, NULL, 0, 0, &e);
    TEST_ASSERT_EQUAL(SPOTIFY_ERROR_OTHER, e.kind);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_track_is_parsed);
    RUN_TEST(test_empty_body_means_no_device);
    RUN_TEST(test_ad_has_no_track_and_null_volume);
    RUN_TEST(test_episode_uses_show_and_episode_art);
    RUN_TEST(test_unicode_title_is_truncated_safely);
    RUN_TEST(test_bad_json_leaves_player_unchanged);
    RUN_TEST(test_like_state_and_context_name_survive_a_poll);
    RUN_TEST(test_progress_past_duration_is_clamped);
    RUN_TEST(test_classify_errors);
    return UNITY_END();
}
