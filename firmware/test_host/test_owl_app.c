#include <stdio.h>
#include <string.h>

#include "owl_app.h"
#include "test_util.h"
#include "unity.h"

#define NOW 1000
#define TRACK_URI "spotify:track:6rqhFgbbKwnb9MLmUQDhG6"
#define PLAYLIST_A "spotify:playlist:3cEYpjA9oz9GiPac4AsH4n"
#define PLAYLIST_B "spotify:playlist:37i9dQZF1DXbITWG1ZJKYt"

static owl_app_t app;
static owl_player_t player;
static owl_effects_t fx;
static owl_list_page_t page;

static void reset_playing(void)
{
    owl_app_init(&app);
    owl_app_set_link(&app, OWL_LINK_API, false);
    owl_player_init(&player);
    player.status = OWL_PLAYER_PLAYING;
    player.has_track = true;
    player.has_device = true;
    player.device.supports_volume = true;
    player.device.volume_percent = 50;
    player.track.kind = OWL_ITEM_TRACK;
    strcpy(player.track.uri, TRACK_URI);
    strcpy(player.track.album, "Moonlit Barn");
    player.track.duration_ms = 200000;
    player.progress_ms = 60000;
    player.progress_at_ms = 0;
    strcpy(player.context_uri, PLAYLIST_A);
}

static void press(owl_input_kind_t kind)
{
    owl_input_t in = {kind, 0};
    owl_app_handle(&app, &player, &in, NOW, &fx);
}

static void turn(int32_t steps)
{
    owl_input_t in = {OWL_IN_RING, steps};
    owl_app_handle(&app, &player, &in, NOW, &fx);
}

static void add_item(owl_list_page_t *p, const char *title, const char *uri, bool browsable)
{
    owl_list_item_t *it = &p->items[p->count++];
    strcpy(it->title, title);
    strcpy(it->uri, uri);
    it->browsable = browsable;
}

static owl_screen_t screen(void)
{
    return owl_app_frame(&app)->screen;
}

static void open_library_entry(owl_lib_entry_t entry)
{
    press(OWL_IN_SWIPE_UP);
    turn((int32_t)entry);
    press(OWL_IN_TAP);
}

static void test_tap_pauses_when_playing(void)
{
    reset_playing();
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL_UINT8(1, fx.n_cmds);
    TEST_ASSERT_EQUAL(OWL_CMD_PAUSE, fx.cmds[0].type);
    TEST_ASSERT_EQUAL(OWL_PLAYER_PAUSED, player.status);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_CONFIRM, fx.haptic);
}

static void test_ring_changes_volume_in_steps(void)
{
    reset_playing();
    turn(3);
    TEST_ASSERT_EQUAL(OWL_CMD_VOLUME, fx.cmds[0].type);
    TEST_ASSERT_EQUAL_INT32(56, fx.cmds[0].value);
    TEST_ASSERT_EQUAL_INT8(56, player.device.volume_percent);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_TICK, fx.haptic);
    TEST_ASSERT_EQUAL_INT64(NOW + OWL_VOLUME_OVERLAY_MS, app.volume_overlay_until_ms);
}

static void test_ring_volume_clamps_with_bump(void)
{
    reset_playing();
    player.device.volume_percent = 98;
    turn(50);
    TEST_ASSERT_EQUAL_INT32(100, fx.cmds[0].value);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_BUMP, fx.haptic);
    turn(1);
    TEST_ASSERT_EQUAL_UINT8(0, fx.n_cmds);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_BUMP, fx.haptic);
}

static void test_ring_uses_media_keys_when_device_refuses_volume(void)
{
    reset_playing();
    player.device.supports_volume = false;
    owl_app_set_link(&app, OWL_LINK_API, true);
    turn(-2);
    TEST_ASSERT_EQUAL_UINT8(0, fx.n_cmds);
    TEST_ASSERT_EQUAL(OWL_KEY_VOL_DOWN, fx.key);
    TEST_ASSERT_EQUAL_UINT8(2, fx.key_repeat);
}

static void test_ring_seeks_when_no_volume_and_no_media_keys(void)
{
    reset_playing();
    player.device.supports_volume = false;
    turn(2);
    TEST_ASSERT_EQUAL(OWL_CMD_SEEK, fx.cmds[0].type);
    TEST_ASSERT_EQUAL_INT32(61000 + 2 * OWL_SEEK_STEP_MS, fx.cmds[0].value);
}

static void test_ears_skip_on_any_screen(void)
{
    reset_playing();
    press(OWL_IN_SWIPE_UP);
    press(OWL_IN_EAR_RIGHT);
    TEST_ASSERT_EQUAL(OWL_CMD_NEXT, fx.cmds[0].type);
    press(OWL_IN_EAR_LEFT);
    TEST_ASSERT_EQUAL(OWL_CMD_PREV, fx.cmds[0].type);
    TEST_ASSERT_EQUAL(OWL_SCREEN_LIBRARY, screen());
}

static void test_right_ear_hold_toggles_like(void)
{
    reset_playing();
    press(OWL_IN_EAR_RIGHT_HOLD);
    TEST_ASSERT_EQUAL(OWL_CMD_LIKE, fx.cmds[0].type);
    TEST_ASSERT_EQUAL_STRING(TRACK_URI, fx.cmds[0].uri);
    TEST_ASSERT_TRUE(player.liked);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_HEARTBEAT, fx.haptic);
    press(OWL_IN_EAR_RIGHT_HOLD);
    TEST_ASSERT_EQUAL(OWL_CMD_UNLIKE, fx.cmds[0].type);
}

static void test_beak_double_toggles_play(void)
{
    reset_playing();
    press(OWL_IN_BEAK_DOUBLE);
    TEST_ASSERT_EQUAL(OWL_CMD_PAUSE, fx.cmds[0].type);
}

static void test_library_cursor_moves_and_bumps_at_ends(void)
{
    reset_playing();
    press(OWL_IN_SWIPE_UP);
    TEST_ASSERT_EQUAL(OWL_SCREEN_LIBRARY, screen());
    turn(1);
    TEST_ASSERT_EQUAL_INT16(1, owl_app_frame(&app)->cursor);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_TICK, fx.haptic);
    turn(-5);
    TEST_ASSERT_EQUAL_INT16(0, owl_app_frame(&app)->cursor);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_BUMP, fx.haptic);
    turn(100);
    TEST_ASSERT_EQUAL_INT16(OWL_LIB_COUNT - 1, owl_app_frame(&app)->cursor);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_BUMP, fx.haptic);
}

static void test_selecting_playlists_requests_them(void)
{
    reset_playing();
    open_library_entry(OWL_LIB_PLAYLISTS);
    TEST_ASSERT_EQUAL(OWL_SCREEN_BROWSE, screen());
    TEST_ASSERT_EQUAL(OWL_LIST_PLAYLISTS, owl_app_frame(&app)->list_kind);
    TEST_ASSERT_EQUAL(OWL_LIST_PLAYLISTS, fx.fetch.kind);
    TEST_ASSERT_NULL(app.list);
}

static void test_owned_playlist_opens_and_followed_one_plays(void)
{
    reset_playing();
    open_library_entry(OWL_LIB_PLAYLISTS);
    owl_list_page_init(&page, OWL_LIST_PLAYLISTS, NULL);
    add_item(&page, "Night Flight Mix", PLAYLIST_A, true);
    add_item(&page, "Owl Jazz", PLAYLIST_B, false);
    TEST_ASSERT_TRUE(owl_app_set_list(&app, &page));

    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL(OWL_LIST_PLAYLIST_ITEMS, owl_app_frame(&app)->list_kind);
    TEST_ASSERT_EQUAL_STRING(PLAYLIST_A, owl_app_frame(&app)->uri);
    TEST_ASSERT_EQUAL(OWL_LIST_PLAYLIST_ITEMS, fx.fetch.kind);
    TEST_ASSERT_EQUAL_STRING(PLAYLIST_A, fx.fetch.uri);

    press(OWL_IN_BEAK);
    TEST_ASSERT_EQUAL(OWL_LIST_PLAYLISTS, owl_app_frame(&app)->list_kind);
    TEST_ASSERT_EQUAL(OWL_LIST_PLAYLISTS, fx.fetch.kind);
    TEST_ASSERT_TRUE(owl_app_set_list(&app, &page));
    turn(1);
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL(OWL_CMD_PLAY_CONTEXT, fx.cmds[0].type);
    TEST_ASSERT_EQUAL_STRING(PLAYLIST_B, fx.cmds[0].uri);
    TEST_ASSERT_EQUAL(OWL_SCREEN_NOW_PLAYING, screen());
    TEST_ASSERT_EQUAL_STRING(PLAYLIST_B, player.context_uri);
    TEST_ASSERT_EQUAL_STRING("Owl Jazz", player.context_name);
}

static void test_track_in_playlist_plays_context_from_that_track(void)
{
    reset_playing();
    open_library_entry(OWL_LIB_PLAYLISTS);
    owl_list_page_init(&page, OWL_LIST_PLAYLISTS, NULL);
    add_item(&page, "Night Flight Mix", PLAYLIST_A, true);
    owl_app_set_list(&app, &page);
    press(OWL_IN_TAP);

    static owl_list_page_t tracks;
    owl_list_page_init(&tracks, OWL_LIST_PLAYLIST_ITEMS, PLAYLIST_A);
    add_item(&tracks, "One", "spotify:track:1111111111111111111111", false);
    add_item(&tracks, "Two", "spotify:track:2222222222222222222222", false);
    add_item(&tracks, "Three", "spotify:track:3333333333333333333333", false);
    TEST_ASSERT_TRUE(owl_app_set_list(&app, &tracks));
    turn(2);
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL(OWL_CMD_PLAY_CONTEXT, fx.cmds[0].type);
    TEST_ASSERT_EQUAL_STRING(PLAYLIST_A, fx.cmds[0].uri);
    TEST_ASSERT_EQUAL_STRING("spotify:track:3333333333333333333333", fx.cmds[0].offset_uri);
}

static void test_liked_songs_play_as_uri_list_from_cursor(void)
{
    reset_playing();
    open_library_entry(OWL_LIB_LIKED);
    owl_list_page_init(&page, OWL_LIST_SAVED_TRACKS, NULL);
    for (int i = 0; i < 25; i++) {
        char uri[OWL_URI_LEN];
        snprintf(uri, sizeof uri, "spotify:track:track%02d", i);
        add_item(&page, "t", uri, false);
    }
    page.items[4].disabled = true;
    owl_app_set_list(&app, &page);
    turn(3);
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL(OWL_CMD_PLAY_URIS, fx.cmds[0].type);
    TEST_ASSERT_EQUAL_UINT8(OWL_CMD_MAX_URIS, fx.cmds[0].n_uris);
    TEST_ASSERT_EQUAL_STRING("spotify:track:track03", fx.cmds[0].uris[0]);
    TEST_ASSERT_EQUAL_STRING("spotify:track:track05", fx.cmds[0].uris[1]);
}

static void test_stale_list_is_ignored(void)
{
    reset_playing();
    open_library_entry(OWL_LIB_PLAYLISTS);
    owl_list_page_init(&page, OWL_LIST_ALBUMS, NULL);
    TEST_ASSERT_FALSE(owl_app_set_list(&app, &page));
    TEST_ASSERT_NULL(app.list);

    owl_list_page_init(&page, OWL_LIST_PLAYLISTS, NULL);
    add_item(&page, "Night Flight Mix", PLAYLIST_A, true);
    owl_app_set_list(&app, &page);
    press(OWL_IN_TAP);
    static owl_list_page_t other;
    owl_list_page_init(&other, OWL_LIST_PLAYLIST_ITEMS, PLAYLIST_B);
    TEST_ASSERT_FALSE(owl_app_set_list(&app, &other));

    press(OWL_IN_BEAK_HOLD);
    owl_list_page_init(&page, OWL_LIST_PLAYLISTS, NULL);
    TEST_ASSERT_FALSE(owl_app_set_list(&app, &page));
}

static void test_device_selection_transfers_playback(void)
{
    reset_playing();
    open_library_entry(OWL_LIB_DEVICES);
    TEST_ASSERT_EQUAL(OWL_LIST_DEVICES, fx.fetch.kind);
    owl_list_page_init(&page, OWL_LIST_DEVICES, NULL);
    add_item(&page, "Study Laptop", "f00dfeed0123456789abcdef0123456789abcdef", false);
    owl_app_set_list(&app, &page);
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL(OWL_CMD_TRANSFER, fx.cmds[0].type);
    TEST_ASSERT_EQUAL_STRING("f00dfeed0123456789abcdef0123456789abcdef", fx.cmds[0].uri);
    TEST_ASSERT_EQUAL(OWL_SCREEN_NOW_PLAYING, screen());
}

static void test_preset_wheel_plays_on_release(void)
{
    reset_playing();
    app.presets[2].assigned = true;
    strcpy(app.presets[2].uri, PLAYLIST_B);
    strcpy(app.presets[2].label, "Owl Jazz");
    press(OWL_IN_EAR_LEFT_HOLD);
    TEST_ASSERT_EQUAL(OWL_SCREEN_PRESETS, screen());
    TEST_ASSERT_TRUE(app.wheel_open);
    turn(2);
    TEST_ASSERT_EQUAL_UINT8(2, app.preset_cursor);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_PRESET, fx.haptic);
    press(OWL_IN_EAR_LEFT_RELEASE);
    TEST_ASSERT_EQUAL(OWL_CMD_PLAY_CONTEXT, fx.cmds[0].type);
    TEST_ASSERT_EQUAL_STRING(PLAYLIST_B, fx.cmds[0].uri);
    TEST_ASSERT_EQUAL(OWL_SCREEN_NOW_PLAYING, screen());
    TEST_ASSERT_FALSE(app.wheel_open);
}

static void test_preset_wheel_wraps_and_unassigned_slot_buzzes(void)
{
    reset_playing();
    press(OWL_IN_SWIPE_UP);
    press(OWL_IN_EAR_LEFT_HOLD);
    turn(-1);
    TEST_ASSERT_EQUAL_UINT8(OWL_PRESET_COUNT - 1, app.preset_cursor);
    press(OWL_IN_EAR_LEFT_RELEASE);
    TEST_ASSERT_EQUAL_UINT8(0, fx.n_cmds);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_BUZZ, fx.haptic);
    TEST_ASSERT_EQUAL(OWL_SCREEN_LIBRARY, screen());
    TEST_ASSERT_FALSE(app.wheel_open);
}

static void test_long_press_on_presets_screen_assigns_current_context(void)
{
    reset_playing();
    open_library_entry(OWL_LIB_PRESETS);
    TEST_ASSERT_EQUAL(OWL_SCREEN_PRESETS, screen());
    TEST_ASSERT_FALSE(app.wheel_open);
    press(OWL_IN_LONG_PRESS);
    TEST_ASSERT_TRUE(app.presets[0].assigned);
    TEST_ASSERT_EQUAL_STRING(PLAYLIST_A, app.presets[0].uri);
    TEST_ASSERT_EQUAL_STRING("Moonlit Barn", app.presets[0].label);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_CONFIRM, fx.haptic);
}

static void test_ring_locked_ignores_ring(void)
{
    reset_playing();
    app.ring_locked = true;
    turn(3);
    TEST_ASSERT_EQUAL_UINT8(0, fx.n_cmds);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_NONE, fx.haptic);
}

static void test_ble_link_sends_media_keys(void)
{
    reset_playing();
    owl_app_set_link(&app, OWL_LINK_BLE, true);
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL(OWL_KEY_PLAY_PAUSE, fx.key);
    TEST_ASSERT_EQUAL_UINT8(0, fx.n_cmds);
    press(OWL_IN_EAR_RIGHT);
    TEST_ASSERT_EQUAL(OWL_KEY_NEXT, fx.key);
    press(OWL_IN_SWIPE_UP);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_BUZZ, fx.haptic);
    TEST_ASSERT_EQUAL(OWL_SCREEN_NOW_PLAYING, screen());
}

static void test_no_device_tap_opens_devices(void)
{
    reset_playing();
    player.status = OWL_PLAYER_NO_DEVICE;
    player.has_device = false;
    turn(1);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_BUZZ, fx.haptic);
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL(OWL_SCREEN_BROWSE, screen());
    TEST_ASSERT_EQUAL(OWL_LIST_DEVICES, fx.fetch.kind);
}

static void test_restricted_device_refuses_commands(void)
{
    reset_playing();
    player.device.is_restricted = true;
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL_UINT8(0, fx.n_cmds);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_BUZZ, fx.haptic);
}

static void test_like_refuses_local_files(void)
{
    reset_playing();
    strcpy(player.track.uri, "spotify:local:The+Barn+Owls:Demos:Barn+Demo:201");
    press(OWL_IN_EAR_RIGHT_HOLD);
    TEST_ASSERT_EQUAL_UINT8(0, fx.n_cmds);
    TEST_ASSERT_FALSE(player.liked);
    TEST_ASSERT_EQUAL(OWL_HAPTIC_BUZZ, fx.haptic);
}

static void test_context_name_survives_playing_from_a_track(void)
{
    reset_playing();
    open_library_entry(OWL_LIB_PLAYLISTS);
    owl_list_page_init(&page, OWL_LIST_PLAYLISTS, NULL);
    add_item(&page, "Night Flight Mix", PLAYLIST_A, true);
    owl_app_set_list(&app, &page);
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL_STRING("Night Flight Mix", owl_app_frame(&app)->title);

    static owl_list_page_t tracks;
    owl_list_page_init(&tracks, OWL_LIST_PLAYLIST_ITEMS, PLAYLIST_A);
    add_item(&tracks, "One", "spotify:track:1111111111111111111111", false);
    owl_app_set_list(&app, &tracks);
    press(OWL_IN_TAP);
    TEST_ASSERT_EQUAL(OWL_CMD_PLAY_CONTEXT, fx.cmds[0].type);
    TEST_ASSERT_EQUAL_STRING("Night Flight Mix", player.context_name);

    open_library_entry(OWL_LIB_PRESETS);
    press(OWL_IN_LONG_PRESS);
    TEST_ASSERT_EQUAL_STRING("Night Flight Mix", app.presets[0].label);
}

static void test_library_labels(void)
{
    TEST_ASSERT_EQUAL_STRING("Playlists", owl_lib_entry_label(OWL_LIB_PLAYLISTS));
    TEST_ASSERT_EQUAL_STRING("Presets", owl_lib_entry_label(OWL_LIB_PRESETS));
    TEST_ASSERT_EQUAL_STRING("", owl_lib_entry_label(OWL_LIB_COUNT));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_tap_pauses_when_playing);
    RUN_TEST(test_ring_changes_volume_in_steps);
    RUN_TEST(test_ring_volume_clamps_with_bump);
    RUN_TEST(test_ring_uses_media_keys_when_device_refuses_volume);
    RUN_TEST(test_ring_seeks_when_no_volume_and_no_media_keys);
    RUN_TEST(test_ears_skip_on_any_screen);
    RUN_TEST(test_right_ear_hold_toggles_like);
    RUN_TEST(test_beak_double_toggles_play);
    RUN_TEST(test_library_cursor_moves_and_bumps_at_ends);
    RUN_TEST(test_selecting_playlists_requests_them);
    RUN_TEST(test_owned_playlist_opens_and_followed_one_plays);
    RUN_TEST(test_track_in_playlist_plays_context_from_that_track);
    RUN_TEST(test_liked_songs_play_as_uri_list_from_cursor);
    RUN_TEST(test_stale_list_is_ignored);
    RUN_TEST(test_device_selection_transfers_playback);
    RUN_TEST(test_preset_wheel_plays_on_release);
    RUN_TEST(test_preset_wheel_wraps_and_unassigned_slot_buzzes);
    RUN_TEST(test_long_press_on_presets_screen_assigns_current_context);
    RUN_TEST(test_ring_locked_ignores_ring);
    RUN_TEST(test_ble_link_sends_media_keys);
    RUN_TEST(test_no_device_tap_opens_devices);
    RUN_TEST(test_restricted_device_refuses_commands);
    RUN_TEST(test_like_refuses_local_files);
    RUN_TEST(test_context_name_survives_playing_from_a_track);
    RUN_TEST(test_library_labels);
    return UNITY_END();
}
