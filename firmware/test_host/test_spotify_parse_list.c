#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "spotify_parse.h"
#include "test_util.h"
#include "unity.h"

#define ME "owlfan"
#define PLAYLIST_A "spotify:playlist:3cEYpjA9oz9GiPac4AsH4n"

static owl_list_page_t page;

static spotify_parse_result_t parse(owl_list_kind_t kind, const char *fixture, const char *source)
{
    size_t len;
    char *json = read_fixture(fixture, &len);
    spotify_parse_result_t r = spotify_parse_list(kind, json, len, ME, source, &page);
    free(json);
    return r;
}

static void test_playlists_mark_owned_and_collaborative_as_browsable(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse(OWL_LIST_PLAYLISTS, "playlists.json", NULL));
    TEST_ASSERT_EQUAL(OWL_LIST_PLAYLISTS, page.kind);
    TEST_ASSERT_EQUAL_UINT16(3, page.count);
    TEST_ASSERT_EQUAL_UINT32(3, page.total);
    TEST_ASSERT_FALSE(page.has_more);

    TEST_ASSERT_EQUAL_STRING("Night Flight Mix", page.items[0].title);
    TEST_ASSERT_TRUE(page.items[0].browsable);
    TEST_ASSERT_EQUAL_STRING("42 songs", page.items[0].subtitle);
    TEST_ASSERT_EQUAL_STRING("https://mosaic.scdn.co/300/nightflightmix", page.items[0].art_url);
    TEST_ASSERT_EQUAL_STRING(PLAYLIST_A, page.items[0].uri);

    TEST_ASSERT_TRUE(page.items[1].browsable);
    TEST_ASSERT_EQUAL_STRING("17 songs", page.items[1].subtitle);
    TEST_ASSERT_EQUAL_STRING("https://i.scdn.co/image/barnparty", page.items[1].art_url);

    TEST_ASSERT_FALSE(page.items[2].browsable);
    TEST_ASSERT_EQUAL_STRING("by Jazz Owls", page.items[2].subtitle);
    TEST_ASSERT_EQUAL_STRING("", page.items[2].art_url);
}

static void test_saved_tracks_with_pagination(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse(OWL_LIST_SAVED_TRACKS, "saved_tracks.json", NULL));
    TEST_ASSERT_EQUAL_UINT16(2, page.count);
    TEST_ASSERT_EQUAL_UINT32(120, page.total);
    TEST_ASSERT_TRUE(page.has_more);
    TEST_ASSERT_EQUAL_STRING("Night Flight", page.items[0].title);
    TEST_ASSERT_EQUAL_STRING("The Barn Owls, Luna Feathers", page.items[0].subtitle);
    TEST_ASSERT_EQUAL_STRING("spotify:track:4iV5W9uYEdYUVa79Axb7Rh", page.items[1].uri);
    TEST_ASSERT_FALSE(page.items[0].browsable);
}

static void test_albums_are_browsable(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse(OWL_LIST_ALBUMS, "albums.json", NULL));
    TEST_ASSERT_EQUAL_UINT16(1, page.count);
    TEST_ASSERT_EQUAL_STRING("Moonlit Barn", page.items[0].title);
    TEST_ASSERT_EQUAL_STRING("The Barn Owls", page.items[0].subtitle);
    TEST_ASSERT_EQUAL_STRING("spotify:album:2up3OPMp9Tb4dAKM2erWXQ", page.items[0].uri);
    TEST_ASSERT_TRUE(page.items[0].browsable);
}

static void test_recently_played(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse(OWL_LIST_RECENT, "recently_played.json", NULL));
    TEST_ASSERT_EQUAL_UINT16(2, page.count);
    TEST_ASSERT_EQUAL_UINT32(2, page.total);
    TEST_ASSERT_EQUAL_STRING("Hoot Loop", page.items[0].title);
}

static void test_queue_lists_upcoming_items_only(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse(OWL_LIST_QUEUE, "queue.json", NULL));
    TEST_ASSERT_EQUAL_UINT16(2, page.count);
    TEST_ASSERT_EQUAL_STRING("Hoot Loop", page.items[0].title);
    TEST_ASSERT_EQUAL_STRING("Night Birds Podcast", page.items[1].subtitle);
}

static void test_devices_mark_active_and_restricted(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse(OWL_LIST_DEVICES, "devices.json", NULL));
    TEST_ASSERT_EQUAL_UINT16(3, page.count);
    TEST_ASSERT_EQUAL_STRING("Pixel 9", page.items[0].title);
    TEST_ASSERT_EQUAL_STRING("Smartphone", page.items[0].subtitle);
    TEST_ASSERT_EQUAL_STRING("a1b2c3d4e5f60718293a4b5c6d7e8f9012345678", page.items[0].uri);
    TEST_ASSERT_TRUE(page.items[0].active);
    TEST_ASSERT_FALSE(page.items[1].active);
    TEST_ASSERT_TRUE(page.items[2].disabled);
}

static void test_playlist_items_skip_removed_and_disable_local(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, parse(OWL_LIST_PLAYLIST_ITEMS, "playlist_items.json", PLAYLIST_A));
    TEST_ASSERT_EQUAL_STRING(PLAYLIST_A, page.source_uri);
    TEST_ASSERT_EQUAL_UINT16(2, page.count);
    TEST_ASSERT_EQUAL_STRING("Night Flight", page.items[0].title);
    TEST_ASSERT_FALSE(page.items[0].disabled);
    TEST_ASSERT_EQUAL_STRING("Barn Demo", page.items[1].title);
    TEST_ASSERT_TRUE(page.items[1].disabled);
}

static void test_old_playlist_item_field_name_still_works(void)
{
    static const char json[] = "{\"items\":[{\"is_local\":false,\"track\":{\"type\":\"track\",\"name\":\"Legacy\","
                               "\"uri\":\"spotify:track:aaa\",\"artists\":[{\"name\":\"Old Owl\"}]}}],\"next\":null}";
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK,
                      spotify_parse_list(OWL_LIST_PLAYLIST_ITEMS, json, sizeof json - 1, ME, PLAYLIST_A, &page));
    TEST_ASSERT_EQUAL_UINT16(1, page.count);
    TEST_ASSERT_EQUAL_STRING("Legacy", page.items[0].title);
}

static void test_album_tracks(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK,
                      parse(OWL_LIST_ALBUM_TRACKS, "album_tracks.json", "spotify:album:2up3OPMp9Tb4dAKM2erWXQ"));
    TEST_ASSERT_EQUAL_UINT16(2, page.count);
    TEST_ASSERT_EQUAL_STRING("Silent Wings", page.items[1].title);
    TEST_ASSERT_EQUAL_STRING("spotify:album:2up3OPMp9Tb4dAKM2erWXQ", page.source_uri);
}

static void test_missing_array_is_bad_shape(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_SHAPE, spotify_parse_list(OWL_LIST_DEVICES, "{}", 2, ME, NULL, &page));
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_JSON, spotify_parse_list(OWL_LIST_DEVICES, "{", 1, ME, NULL, &page));
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_SHAPE, spotify_parse_list(OWL_LIST_NONE, "{}", 2, ME, NULL, &page));
}

static void test_oversized_device_list_is_capped(void)
{
    static char json[16384];
    size_t used = (size_t)snprintf(json, sizeof json, "{\"devices\":[");
    for (int i = 0; i < 60; i++) {
        used += (size_t)snprintf(json + used, sizeof json - used,
                                 "%s{\"id\":\"dev%02d\",\"name\":\"Speaker %d\",\"type\":\"Speaker\",\"is_active\":false}",
                                 i ? "," : "", i, i);
    }
    used += (size_t)snprintf(json + used, sizeof json - used, "]}");
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, spotify_parse_list(OWL_LIST_DEVICES, json, used, ME, NULL, &page));
    TEST_ASSERT_EQUAL_UINT16(OWL_LIST_MAX_ITEMS, page.count);
    TEST_ASSERT_EQUAL_UINT32(60, page.total);
    TEST_ASSERT_TRUE(page.has_more);
    TEST_ASSERT_EQUAL_STRING("Speaker 49", page.items[49].title);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_playlists_mark_owned_and_collaborative_as_browsable);
    RUN_TEST(test_saved_tracks_with_pagination);
    RUN_TEST(test_albums_are_browsable);
    RUN_TEST(test_recently_played);
    RUN_TEST(test_queue_lists_upcoming_items_only);
    RUN_TEST(test_devices_mark_active_and_restricted);
    RUN_TEST(test_playlist_items_skip_removed_and_disable_local);
    RUN_TEST(test_old_playlist_item_field_name_still_works);
    RUN_TEST(test_album_tracks);
    RUN_TEST(test_missing_array_is_bad_shape);
    RUN_TEST(test_oversized_device_list_is_capped);
    return UNITY_END();
}
