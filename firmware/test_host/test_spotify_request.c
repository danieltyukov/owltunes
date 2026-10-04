#include <string.h>

#include "spotify_api.h"
#include "test_util.h"
#include "unity.h"

static spotify_request_t req;

static bool build(owl_cmd_type_t type, int32_t value, const char *uri)
{
    owl_cmd_t c;
    owl_cmd_set(&c, type, value, uri);
    return spotify_request_for_command(&c, &req);
}

static void expect(spotify_method_t method, const char *path, const char *body)
{
    TEST_ASSERT_EQUAL_STRING(spotify_method_name(method), spotify_method_name(req.method));
    TEST_ASSERT_EQUAL_STRING(path, req.path);
    TEST_ASSERT_EQUAL_STRING(body, req.body);
}

static void test_transport_commands(void)
{
    TEST_ASSERT_TRUE(build(OWL_CMD_PLAY, 0, NULL));
    expect(SPOTIFY_PUT, "/v1/me/player/play", "");
    TEST_ASSERT_TRUE(build(OWL_CMD_PAUSE, 0, NULL));
    expect(SPOTIFY_PUT, "/v1/me/player/pause", "");
    TEST_ASSERT_TRUE(build(OWL_CMD_NEXT, 0, NULL));
    expect(SPOTIFY_POST, "/v1/me/player/next", "");
    TEST_ASSERT_TRUE(build(OWL_CMD_PREV, 0, NULL));
    expect(SPOTIFY_POST, "/v1/me/player/previous", "");
}

static void test_value_commands(void)
{
    TEST_ASSERT_TRUE(build(OWL_CMD_SEEK, 83000, NULL));
    expect(SPOTIFY_PUT, "/v1/me/player/seek?position_ms=83000", "");
    TEST_ASSERT_TRUE(build(OWL_CMD_VOLUME, 64, NULL));
    expect(SPOTIFY_PUT, "/v1/me/player/volume?volume_percent=64", "");
    TEST_ASSERT_TRUE(build(OWL_CMD_SHUFFLE, 1, NULL));
    expect(SPOTIFY_PUT, "/v1/me/player/shuffle?state=true", "");
    TEST_ASSERT_TRUE(build(OWL_CMD_REPEAT, OWL_REPEAT_TRACK, NULL));
    expect(SPOTIFY_PUT, "/v1/me/player/repeat?state=track", "");
}

static void test_out_of_range_values_are_rejected(void)
{
    TEST_ASSERT_FALSE(build(OWL_CMD_VOLUME, 101, NULL));
    TEST_ASSERT_FALSE(build(OWL_CMD_SEEK, -1, NULL));
    TEST_ASSERT_FALSE(build(OWL_CMD_REPEAT, 7, NULL));
    TEST_ASSERT_FALSE(build(OWL_CMD_NONE, 0, NULL));
}

static void test_library_and_queue_commands_encode_the_uri(void)
{
    TEST_ASSERT_TRUE(build(OWL_CMD_LIKE, 0, "spotify:track:6rqhFgbbKwnb9MLmUQDhG6"));
    expect(SPOTIFY_PUT, "/v1/me/library?uris=spotify%3Atrack%3A6rqhFgbbKwnb9MLmUQDhG6", "");
    TEST_ASSERT_TRUE(build(OWL_CMD_UNLIKE, 0, "spotify:track:6rqhFgbbKwnb9MLmUQDhG6"));
    expect(SPOTIFY_DELETE, "/v1/me/library?uris=spotify%3Atrack%3A6rqhFgbbKwnb9MLmUQDhG6", "");
    TEST_ASSERT_TRUE(build(OWL_CMD_QUEUE_ADD, 0, "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"));
    expect(SPOTIFY_POST, "/v1/me/player/queue?uri=spotify%3Atrack%3A4iV5W9uYEdYUVa79Axb7Rh", "");
}

static void test_play_context_with_and_without_offset(void)
{
    owl_cmd_t c;
    owl_cmd_set(&c, OWL_CMD_PLAY_CONTEXT, 0, "spotify:playlist:3cEYpjA9oz9GiPac4AsH4n");
    TEST_ASSERT_TRUE(spotify_request_for_command(&c, &req));
    expect(SPOTIFY_PUT, "/v1/me/player/play", "{\"context_uri\":\"spotify:playlist:3cEYpjA9oz9GiPac4AsH4n\"}");
    strcpy(c.offset_uri, "spotify:track:6rqhFgbbKwnb9MLmUQDhG6");
    TEST_ASSERT_TRUE(spotify_request_for_command(&c, &req));
    expect(SPOTIFY_PUT, "/v1/me/player/play",
           "{\"context_uri\":\"spotify:playlist:3cEYpjA9oz9GiPac4AsH4n\","
           "\"offset\":{\"uri\":\"spotify:track:6rqhFgbbKwnb9MLmUQDhG6\"}}");
}

static void test_play_uris_lists_every_uri(void)
{
    owl_cmd_t c;
    owl_cmd_set(&c, OWL_CMD_PLAY_URIS, 0, NULL);
    strcpy(c.uris[0], "spotify:track:aaa");
    strcpy(c.uris[1], "spotify:track:bbb");
    c.n_uris = 2;
    TEST_ASSERT_TRUE(spotify_request_for_command(&c, &req));
    expect(SPOTIFY_PUT, "/v1/me/player/play", "{\"uris\":[\"spotify:track:aaa\",\"spotify:track:bbb\"]}");
    c.n_uris = 0;
    TEST_ASSERT_FALSE(spotify_request_for_command(&c, &req));
}

static void test_play_uris_fits_the_maximum(void)
{
    owl_cmd_t c;
    owl_cmd_set(&c, OWL_CMD_PLAY_URIS, 0, NULL);
    for (int i = 0; i < OWL_CMD_MAX_URIS; i++) {
        memset(c.uris[i], 'x', OWL_URI_LEN - 1);
        memcpy(c.uris[i], "spotify:track:", 14);
        c.uris[i][OWL_URI_LEN - 1] = '\0';
    }
    c.n_uris = OWL_CMD_MAX_URIS;
    TEST_ASSERT_TRUE(spotify_request_for_command(&c, &req));
    TEST_ASSERT_EQUAL_INT('}', req.body[strlen(req.body) - 1]);
}

static void test_transfer_body(void)
{
    TEST_ASSERT_TRUE(build(OWL_CMD_TRANSFER, 0, "f00dfeed0123456789abcdef0123456789abcdef"));
    expect(SPOTIFY_PUT, "/v1/me/player", "{\"device_ids\":[\"f00dfeed0123456789abcdef0123456789abcdef\"],\"play\":true}");
}

static void test_unsafe_uris_are_rejected(void)
{
    TEST_ASSERT_FALSE(build(OWL_CMD_PLAY_CONTEXT, 0, "spotify:playlist:x\"},{\"evil\":\"1"));
    TEST_ASSERT_FALSE(build(OWL_CMD_LIKE, 0, "spotify:track:a&uris=b"));
    TEST_ASSERT_FALSE(build(OWL_CMD_TRANSFER, 0, ""));
    TEST_ASSERT_FALSE(build(OWL_CMD_QUEUE_ADD, 0, "spotify:local:The+Barn+Owls:Demos:Barn+Demo:201"));
}

static void test_fetch_paths(void)
{
    owl_fetch_t f = {.kind = OWL_LIST_PLAYLISTS, .offset = 50};
    TEST_ASSERT_TRUE(spotify_request_for_fetch(&f, &req));
    expect(SPOTIFY_GET, "/v1/me/playlists?limit=50&offset=50", "");
    f.kind = OWL_LIST_SAVED_TRACKS;
    f.offset = 0;
    TEST_ASSERT_TRUE(spotify_request_for_fetch(&f, &req));
    expect(SPOTIFY_GET, "/v1/me/tracks?limit=50&offset=0", "");
    f.kind = OWL_LIST_ALBUMS;
    TEST_ASSERT_TRUE(spotify_request_for_fetch(&f, &req));
    expect(SPOTIFY_GET, "/v1/me/albums?limit=50&offset=0", "");
    f.kind = OWL_LIST_RECENT;
    TEST_ASSERT_TRUE(spotify_request_for_fetch(&f, &req));
    expect(SPOTIFY_GET, "/v1/me/player/recently-played?limit=50", "");
    f.kind = OWL_LIST_QUEUE;
    TEST_ASSERT_TRUE(spotify_request_for_fetch(&f, &req));
    expect(SPOTIFY_GET, "/v1/me/player/queue", "");
    f.kind = OWL_LIST_DEVICES;
    TEST_ASSERT_TRUE(spotify_request_for_fetch(&f, &req));
    expect(SPOTIFY_GET, "/v1/me/player/devices", "");
}

static void test_fetch_items_need_a_matching_uri(void)
{
    owl_fetch_t f = {.kind = OWL_LIST_PLAYLIST_ITEMS};
    strcpy(f.uri, "spotify:playlist:3cEYpjA9oz9GiPac4AsH4n");
    TEST_ASSERT_TRUE(spotify_request_for_fetch(&f, &req));
    expect(SPOTIFY_GET, "/v1/playlists/3cEYpjA9oz9GiPac4AsH4n/items?limit=50&offset=0&additional_types=episode", "");
    f.kind = OWL_LIST_ALBUM_TRACKS;
    strcpy(f.uri, "spotify:album:2up3OPMp9Tb4dAKM2erWXQ");
    TEST_ASSERT_TRUE(spotify_request_for_fetch(&f, &req));
    expect(SPOTIFY_GET, "/v1/albums/2up3OPMp9Tb4dAKM2erWXQ/tracks?limit=50&offset=0", "");
    strcpy(f.uri, "spotify:playlist:2up3OPMp9Tb4dAKM2erWXQ");
    TEST_ASSERT_FALSE(spotify_request_for_fetch(&f, &req));
    f.kind = OWL_LIST_NONE;
    TEST_ASSERT_FALSE(spotify_request_for_fetch(&f, &req));
}

static void test_player_state_request(void)
{
    spotify_request_player_state(&req);
    expect(SPOTIFY_GET, "/v1/me/player?additional_types=episode", "");
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_transport_commands);
    RUN_TEST(test_value_commands);
    RUN_TEST(test_out_of_range_values_are_rejected);
    RUN_TEST(test_library_and_queue_commands_encode_the_uri);
    RUN_TEST(test_play_context_with_and_without_offset);
    RUN_TEST(test_play_uris_lists_every_uri);
    RUN_TEST(test_play_uris_fits_the_maximum);
    RUN_TEST(test_transfer_body);
    RUN_TEST(test_unsafe_uris_are_rejected);
    RUN_TEST(test_fetch_paths);
    RUN_TEST(test_fetch_items_need_a_matching_uri);
    RUN_TEST(test_player_state_request);
    return UNITY_END();
}
