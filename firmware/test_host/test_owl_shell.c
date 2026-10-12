#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "owl_shell.h"
#include "test_util.h"
#include "unity.h"

static owl_shell_cmd_t cmd;
static owl_cmd_t out_cmd;
static char line[OWL_SHELL_LINE_MAX + 64];
static cJSON *json;

static owl_shell_verb_t verb_of(const char *text)
{
    owl_shell_parse(text, &cmd);
    TEST_ASSERT_FALSE_MESSAGE(cmd.bad_arg, text);
    return cmd.verb;
}

/* The command a malformed line names; the test fails unless the argument was refused. */
static owl_shell_verb_t refused_verb_of(const char *text)
{
    owl_shell_parse(text, &cmd);
    TEST_ASSERT_TRUE_MESSAGE(cmd.bad_arg, text);
    return cmd.verb;
}

/* Parse the line in `line` (after checking its framing) into `json`. */
static void parse_line(void)
{
    size_t len = strlen(line);
    TEST_ASSERT_TRUE(len <= OWL_SHELL_LINE_MAX);
    TEST_ASSERT_EQUAL_MEMORY("@owl ", line, 5);
    TEST_ASSERT_EQUAL_CHAR('\n', line[len - 1]);
    cJSON_Delete(json);
    json = cJSON_Parse(line + 5);
    TEST_ASSERT_NOT_NULL(json);
}

static const char *str_field(const char *name)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(json, name);
    return cJSON_IsString(v) ? v->valuestring : NULL;
}

static int64_t num_field(const char *name)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(json, name);
    TEST_ASSERT_TRUE(cJSON_IsNumber(v));
    return (int64_t)v->valuedouble;
}

static void test_empty_lines_are_ignored(void)
{
    TEST_ASSERT_EQUAL(OWL_SHELL_NONE, verb_of(""));
    TEST_ASSERT_EQUAL(OWL_SHELL_NONE, verb_of("   \t"));
    TEST_ASSERT_EQUAL(OWL_SHELL_NONE, verb_of("\r"));
    TEST_ASSERT_EQUAL(OWL_SHELL_NONE, verb_of(NULL));
}

static void test_commands_are_lowercase_words(void)
{
    TEST_ASSERT_EQUAL(OWL_SHELL_INFO, verb_of("info"));
    TEST_ASSERT_EQUAL(OWL_SHELL_HELP, verb_of("  help \r"));
    TEST_ASSERT_EQUAL(OWL_SHELL_UNKNOWN, verb_of("INFO"));
    TEST_ASSERT_EQUAL(OWL_SHELL_UNKNOWN, verb_of("information"));
    TEST_ASSERT_EQUAL(OWL_SHELL_UNKNOWN, verb_of("{\"id\":1,\"cmd\":\"hello\"}"));
    TEST_ASSERT_EQUAL_STRING("info", owl_shell_verb_name(OWL_SHELL_INFO));
    TEST_ASSERT_EQUAL_STRING("", owl_shell_verb_name(OWL_SHELL_UNKNOWN));
}

static void test_an_unexpected_argument_is_refused(void)
{
    TEST_ASSERT_EQUAL(OWL_SHELL_INFO, refused_verb_of("info now"));
    TEST_ASSERT_EQUAL(OWL_SHELL_HELP, refused_verb_of("help me please"));
}

static void test_cmd_line_is_exact(void)
{
    TEST_ASSERT_TRUE(owl_shell_cmd_line(line, sizeof line, "refused", "info", "bad_arg", 0));
    TEST_ASSERT_EQUAL_STRING(
        "@owl {\"event\":\"cmd\",\"state\":\"refused\",\"cmd\":\"info\",\"error\":\"bad_arg\"}\n", line);
    TEST_ASSERT_TRUE(owl_shell_cmd_line(line, sizeof line, "refused", NULL, "unknown_cmd", 0));
    TEST_ASSERT_EQUAL_STRING("@owl {\"event\":\"cmd\",\"state\":\"refused\",\"error\":\"unknown_cmd\"}\n",
                             line);
    TEST_ASSERT_TRUE(owl_shell_cmd_line(line, sizeof line, "failed", "next", "rate_limited", 5));
    TEST_ASSERT_EQUAL_STRING("@owl {\"event\":\"cmd\",\"state\":\"failed\",\"cmd\":\"next\",\"error\":"
                             "\"rate_limited\",\"retry_s\":5}\n",
                             line);
}

static void test_event_line_is_exact(void)
{
    TEST_ASSERT_TRUE(owl_shell_event_line(line, sizeof line, "devices", "done", NULL, NULL, "count", 2));
    TEST_ASSERT_EQUAL_STRING("@owl {\"event\":\"devices\",\"state\":\"done\",\"count\":2}\n", line);
    TEST_ASSERT_TRUE(
        owl_shell_event_line(line, sizeof line, "time", "synced", "utc", "2026-10-11T09:30:00Z", NULL, 0));
    TEST_ASSERT_EQUAL_STRING(
        "@owl {\"event\":\"time\",\"state\":\"synced\",\"utc\":\"2026-10-11T09:30:00Z\"}\n", line);
}

static void test_info_line(void)
{
    owl_shell_info_t info = {
        .board = "nano_esp32",
        .name = "OwlTunes-7DF8",
        .fw = "v0.3.0",
        .uptime_s = 12,
        .reset = "usb",
        .partition = "ota_0",
        .flash_kb = 16384,
        .psram_kb = 8192,
        .psram_free_kb = 8000,
        .heap_free_kb = 210,
        .heap_min_kb = 190,
        .status = "needs_wifi",
        .led = {0, 0, 64},
        .wifi = "idle",
        .ssid = NULL,
        .rssi = 0,
        .ip = "",
        .linked = false,
        .utc = NULL,
    };
    TEST_ASSERT_TRUE(owl_shell_info_line(line, sizeof line, &info));
    parse_line();
    TEST_ASSERT_EQUAL_STRING("info", str_field("event"));
    TEST_ASSERT_EQUAL_STRING("nano_esp32", str_field("board"));
    TEST_ASSERT_EQUAL_INT64(8192, num_field("psram_kb"));
    TEST_ASSERT_EQUAL_INT64(16384, num_field("flash_kb"));
    TEST_ASSERT_EQUAL_STRING("ota_0", str_field("partition"));
    TEST_ASSERT_EQUAL_STRING("#000040", str_field("led"));
    TEST_ASSERT_EQUAL_STRING("", str_field("ssid"));
    TEST_ASSERT_EQUAL_STRING("", str_field("utc"));
    TEST_ASSERT_TRUE(cJSON_IsFalse(cJSON_GetObjectItem(json, "linked")));
}

static void test_info_line_escapes_a_hostile_ssid(void)
{
    owl_shell_info_t info = {.board = "qemu", .ssid = "\"}\n@owl {\"event\":\"spoof\"}", .led = {0, 0, 0}};
    TEST_ASSERT_TRUE(owl_shell_info_line(line, sizeof line, &info));
    TEST_ASSERT_EQUAL_PTR(line + strlen(line) - 1, strchr(line, '\n')); /* one line, not two */
    parse_line();
    TEST_ASSERT_EQUAL_STRING("\"}\n@owl {\"event\":\"spoof\"}", str_field("ssid"));
}

static void test_help_lists_the_commands(void)
{
    TEST_ASSERT_TRUE(owl_shell_help_line(line, sizeof line));
    parse_line();
    TEST_ASSERT_NOT_NULL(strstr(str_field("commands"), "info"));
}

static void test_a_buffer_too_small_fails_cleanly(void)
{
    char tiny[16] = "untouched";
    TEST_ASSERT_FALSE(owl_shell_cmd_line(tiny, sizeof tiny, "done", "next", NULL, 0));
    TEST_ASSERT_EQUAL_STRING("", tiny);
}

/* ---- playback commands -------------------------------------------------------------------- */

static owl_player_t playing_track(void)
{
    owl_player_t p;
    owl_player_init(&p);
    p.status = OWL_PLAYER_PLAYING;
    p.has_track = true;
    p.track.kind = OWL_ITEM_TRACK;
    strcpy(p.track.uri, "spotify:track:6rqhFgbbKwnb9MLmUQDhG6");
    strcpy(p.track.title, "Night Flight");
    strcpy(p.track.subtitle, "The Barn Owls");
    strcpy(p.track.album, "Moonlit Barn");
    p.track.duration_ms = 215000;
    p.progress_ms = 42000;
    p.progress_at_ms = 1000;
    p.has_device = true;
    strcpy(p.device.id, "0d1841b0976bae2a3a310dd74c0f3df354899bc8");
    strcpy(p.device.name, "Kitchen speaker");
    strcpy(p.device.type, "Speaker");
    p.device.is_active = true;
    p.device.supports_volume = true;
    p.device.volume_percent = 64;
    return p;
}

static owl_list_page_t two_devices(void)
{
    owl_list_page_t page;
    owl_list_page_init(&page, OWL_LIST_DEVICES, NULL);
    page.count = 2;
    strcpy(page.items[0].title, "Pixel 9");
    strcpy(page.items[0].subtitle, "Smartphone");
    strcpy(page.items[0].uri, "aaaa1111");
    page.items[0].active = true;
    strcpy(page.items[1].title, "Desk");
    strcpy(page.items[1].subtitle, "Computer");
    strcpy(page.items[1].uri, "bbbb2222");
    return page;
}

static const char *resolve(const char *text, const owl_player_t *p, const owl_list_page_t *devices)
{
    owl_shell_parse(text, &cmd);
    return owl_shell_resolve(&cmd, p, devices, &out_cmd);
}

static void test_commands_without_arguments(void)
{
    TEST_ASSERT_EQUAL(OWL_SHELL_NEXT, verb_of("next"));
    TEST_ASSERT_EQUAL(OWL_SHELL_PAUSE, verb_of("  pause \r"));
    TEST_ASSERT_EQUAL(OWL_SHELL_PREV, verb_of("prev"));
    TEST_ASSERT_EQUAL(OWL_SHELL_PREV, verb_of("previous"));
    TEST_ASSERT_EQUAL(OWL_SHELL_TOGGLE, verb_of("toggle"));
    TEST_ASSERT_EQUAL(OWL_SHELL_DEVICES, verb_of("devices"));
    TEST_ASSERT_EQUAL(OWL_SHELL_INFO, verb_of("info"));
    TEST_ASSERT_EQUAL(OWL_SHELL_STATUS, verb_of("status"));
    TEST_ASSERT_EQUAL(OWL_SHELL_HELP, verb_of("help"));
}

static void test_unknown_words_and_extra_arguments(void)
{
    TEST_ASSERT_EQUAL(OWL_SHELL_UNKNOWN, verb_of("skip"));
    TEST_ASSERT_EQUAL(OWL_SHELL_UNKNOWN, verb_of("NEXT"));
    TEST_ASSERT_EQUAL(OWL_SHELL_UNKNOWN, verb_of("nextt"));
    TEST_ASSERT_EQUAL(OWL_SHELL_NEXT, refused_verb_of("next 3"));
    TEST_ASSERT_EQUAL(OWL_SHELL_VOLUME, refused_verb_of("vol 40 50"));
    TEST_ASSERT_EQUAL_STRING("", owl_shell_verb_name(OWL_SHELL_UNKNOWN));
}

static void test_volume_absolute_and_relative(void)
{
    TEST_ASSERT_EQUAL(OWL_SHELL_VOLUME, verb_of("vol 40"));
    TEST_ASSERT_EQUAL_INT32(40, cmd.value);
    TEST_ASSERT_FALSE(cmd.relative);
    TEST_ASSERT_EQUAL(OWL_SHELL_VOLUME, verb_of("vol +5"));
    TEST_ASSERT_EQUAL_INT32(5, cmd.value);
    TEST_ASSERT_TRUE(cmd.relative);
    TEST_ASSERT_EQUAL(OWL_SHELL_VOLUME, verb_of("volume -10"));
    TEST_ASSERT_EQUAL_INT32(-10, cmd.value);
    TEST_ASSERT_TRUE(cmd.relative);
    TEST_ASSERT_EQUAL(OWL_SHELL_VOLUME, verb_of("vol 0"));
    TEST_ASSERT_EQUAL(OWL_SHELL_VOLUME, verb_of("vol 100"));
    TEST_ASSERT_EQUAL_STRING("volume", owl_shell_verb_name(cmd.verb));
}

static void test_malformed_volumes_are_refused(void)
{
    const char *bad[] = {"vol", "vol 101", "vol +101", "vol 4x", "vol ++5", "vol -", "vol 0040", "vol 4.5"};
    for (size_t i = 0; i < sizeof bad / sizeof bad[0]; i++) {
        TEST_ASSERT_EQUAL_MESSAGE(OWL_SHELL_VOLUME, refused_verb_of(bad[i]), bad[i]);
    }
}

static void test_auth_takes_an_optional_refresh(void)
{
    TEST_ASSERT_EQUAL(OWL_SHELL_AUTH, verb_of("auth"));
    TEST_ASSERT_EQUAL_INT32(0, cmd.value);
    TEST_ASSERT_EQUAL(OWL_SHELL_AUTH, verb_of("auth refresh"));
    TEST_ASSERT_EQUAL_INT32(1, cmd.value);
    TEST_ASSERT_EQUAL(OWL_SHELL_AUTH, refused_verb_of("auth now"));
}

static void test_transfer_takes_a_number_or_a_device_id(void)
{
    TEST_ASSERT_EQUAL(OWL_SHELL_TRANSFER, verb_of("transfer 2"));
    TEST_ASSERT_EQUAL_STRING("2", cmd.arg);
    TEST_ASSERT_EQUAL(OWL_SHELL_TRANSFER, verb_of("transfer 0d1841b0976bae2a3a310dd74c0f3df354899bc8"));
    TEST_ASSERT_EQUAL_STRING("0d1841b0976bae2a3a310dd74c0f3df354899bc8", cmd.arg);
    TEST_ASSERT_EQUAL(OWL_SHELL_TRANSFER, refused_verb_of("transfer"));
    TEST_ASSERT_EQUAL(OWL_SHELL_TRANSFER, refused_verb_of("transfer a&b"));
    TEST_ASSERT_EQUAL(OWL_SHELL_TRANSFER, refused_verb_of("transfer \"x\""));
    TEST_ASSERT_EQUAL(OWL_SHELL_TRANSFER, verb_of("transfer ab_C-9"));
    TEST_ASSERT_EQUAL_STRING("ab_C-9", cmd.arg);
    TEST_ASSERT_EQUAL_INT(63, OWL_SHELL_ARG_LEN);
    char long_id[OWL_SHELL_ARG_LEN + 16] = "transfer ";
    memset(long_id + 9, 'a', OWL_SHELL_ARG_LEN);
    long_id[9 + OWL_SHELL_ARG_LEN] = '\0';
    TEST_ASSERT_EQUAL(OWL_SHELL_TRANSFER, verb_of(long_id)); /* 63 characters are the limit (P16) */
    TEST_ASSERT_EQUAL_size_t(OWL_SHELL_ARG_LEN, strlen(cmd.arg));
    long_id[9 + OWL_SHELL_ARG_LEN] = 'a';
    long_id[10 + OWL_SHELL_ARG_LEN] = '\0';
    TEST_ASSERT_EQUAL(OWL_SHELL_TRANSFER, refused_verb_of(long_id));
}

static void test_playback_verbs_are_marked(void)
{
    TEST_ASSERT_TRUE(owl_shell_is_playback(OWL_SHELL_PLAY));
    TEST_ASSERT_TRUE(owl_shell_is_playback(OWL_SHELL_TRANSFER));
    TEST_ASSERT_FALSE(owl_shell_is_playback(OWL_SHELL_DEVICES));
    TEST_ASSERT_FALSE(owl_shell_is_playback(OWL_SHELL_AUTH));
}

static void test_toggle_follows_the_player(void)
{
    owl_player_t p = playing_track();
    TEST_ASSERT_NULL(resolve("toggle", &p, NULL));
    TEST_ASSERT_EQUAL(OWL_CMD_PAUSE, out_cmd.type);
    p.status = OWL_PLAYER_PAUSED;
    TEST_ASSERT_NULL(resolve("toggle", &p, NULL));
    TEST_ASSERT_EQUAL(OWL_CMD_PLAY, out_cmd.type);
    owl_player_init(&p);
    TEST_ASSERT_NULL(resolve("toggle", &p, NULL));
    TEST_ASSERT_EQUAL(OWL_CMD_PLAY, out_cmd.type);
    TEST_ASSERT_NULL(resolve("next", &p, NULL));
    TEST_ASSERT_EQUAL(OWL_CMD_NEXT, out_cmd.type);
    TEST_ASSERT_NULL(resolve("prev", &p, NULL));
    TEST_ASSERT_EQUAL(OWL_CMD_PREV, out_cmd.type);
}

static void test_no_active_device_refuses_playback(void)
{
    owl_player_t p;
    owl_player_init(&p);
    p.status = OWL_PLAYER_NO_DEVICE;
    TEST_ASSERT_EQUAL_STRING("no_active_device", resolve("play", &p, NULL));
    TEST_ASSERT_EQUAL_STRING("no_active_device", resolve("vol 30", &p, NULL));
    p = playing_track();
    p.device.is_restricted = true;
    TEST_ASSERT_EQUAL_STRING("device_restricted", resolve("next", &p, NULL));
}

static void test_volume_is_clamped_and_needs_a_willing_device(void)
{
    owl_player_t p = playing_track();
    TEST_ASSERT_NULL(resolve("vol 40", &p, NULL));
    TEST_ASSERT_EQUAL(OWL_CMD_VOLUME, out_cmd.type);
    TEST_ASSERT_EQUAL_INT32(40, out_cmd.value);
    p.device.volume_percent = 95;
    TEST_ASSERT_NULL(resolve("vol +10", &p, NULL));
    TEST_ASSERT_EQUAL_INT32(100, out_cmd.value);
    p.device.volume_percent = 5;
    TEST_ASSERT_NULL(resolve("vol -10", &p, NULL));
    TEST_ASSERT_EQUAL_INT32(0, out_cmd.value);
    p.device.volume_percent = -1;
    TEST_ASSERT_EQUAL_STRING("volume_unknown", resolve("vol +5", &p, NULL));
    p.device.supports_volume = false;
    TEST_ASSERT_EQUAL_STRING("volume_unsupported", resolve("vol 40", &p, NULL));
    owl_player_init(&p);
    TEST_ASSERT_NULL(resolve("vol 40", &p, NULL));
    TEST_ASSERT_EQUAL_STRING("volume_unknown", resolve("vol +5", &p, NULL));
}

static void test_like_needs_a_spotify_track(void)
{
    owl_player_t p = playing_track();
    TEST_ASSERT_NULL(resolve("like", &p, NULL));
    TEST_ASSERT_EQUAL(OWL_CMD_LIKE, out_cmd.type);
    TEST_ASSERT_EQUAL_STRING("spotify:track:6rqhFgbbKwnb9MLmUQDhG6", out_cmd.uri);
    TEST_ASSERT_NULL(resolve("unlike", &p, NULL));
    TEST_ASSERT_EQUAL(OWL_CMD_UNLIKE, out_cmd.type);
    strcpy(p.track.uri, "spotify:local:Barn+Owls:::120");
    TEST_ASSERT_EQUAL_STRING("no_track", resolve("like", &p, NULL));
    p = playing_track();
    p.track.kind = OWL_ITEM_EPISODE;
    TEST_ASSERT_EQUAL_STRING("no_track", resolve("like", &p, NULL));
    owl_player_init(&p);
    TEST_ASSERT_EQUAL_STRING("no_track", resolve("like", &p, NULL));
}

static void test_transfer_by_number_or_id(void)
{
    owl_player_t p;
    owl_player_init(&p);
    p.status = OWL_PLAYER_NO_DEVICE; /* transfer is how a person gets out of this state */
    owl_list_page_t devices = two_devices();
    TEST_ASSERT_NULL(resolve("transfer 2", &p, &devices));
    TEST_ASSERT_EQUAL(OWL_CMD_TRANSFER, out_cmd.type);
    TEST_ASSERT_EQUAL_STRING("bbbb2222", out_cmd.uri);
    TEST_ASSERT_EQUAL_STRING("no_such_device", resolve("transfer 3", &p, &devices));
    TEST_ASSERT_EQUAL_STRING("no_such_device", resolve("transfer 0", &p, &devices));
    TEST_ASSERT_EQUAL_STRING("no_such_device", resolve("transfer 1", &p, NULL));
    devices.items[0].disabled = true;
    TEST_ASSERT_EQUAL_STRING("device_restricted", resolve("transfer 1", &p, &devices));
    TEST_ASSERT_NULL(resolve("transfer cccc3333", &p, &devices));
    TEST_ASSERT_EQUAL_STRING("cccc3333", out_cmd.uri);
    TEST_ASSERT_EQUAL_STRING("not_playback", resolve("devices", &p, &devices));
    /* The longest id the console takes fits the command whole; one more character is bad_arg. */
    static const char id63[] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    TEST_ASSERT_EQUAL_size_t(63, strlen(id63));
    char line63[96];
    snprintf(line63, sizeof line63, "transfer %s", id63);
    TEST_ASSERT_NULL(resolve(line63, &p, &devices));
    TEST_ASSERT_EQUAL_STRING(id63, out_cmd.uri);
    owl_shell_parse("transfer aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", &cmd);
    TEST_ASSERT_TRUE(cmd.bad_arg);
}

static void test_player_line_carries_the_state(void)
{
    owl_player_t p = playing_track();
    TEST_ASSERT_TRUE(owl_shell_player_line(line, sizeof line, &p, 3000, OWL_LINK_API, 0));
    parse_line();
    TEST_ASSERT_EQUAL_STRING("player", str_field("event"));
    TEST_ASSERT_EQUAL_STRING("playing", str_field("status"));
    TEST_ASSERT_EQUAL_STRING("track", str_field("kind"));
    TEST_ASSERT_EQUAL_STRING("Night Flight", str_field("title"));
    TEST_ASSERT_EQUAL_STRING("The Barn Owls", str_field("artist"));
    TEST_ASSERT_EQUAL_STRING("spotify:track:6rqhFgbbKwnb9MLmUQDhG6", str_field("uri"));
    TEST_ASSERT_EQUAL_INT64(44000, num_field("progress_ms"));
    TEST_ASSERT_EQUAL_INT64(64, num_field("volume"));
    TEST_ASSERT_TRUE(cJSON_IsNull(cJSON_GetObjectItem(json, "liked")));
    TEST_ASSERT_EQUAL_STRING("Kitchen speaker", str_field("device"));
    TEST_ASSERT_EQUAL_STRING("api", str_field("link"));
    TEST_ASSERT_EQUAL_STRING("off", str_field("repeat"));

    p.liked = true;
    p.liked_known = true;
    p.device.volume_percent = -1;
    TEST_ASSERT_TRUE(owl_shell_player_line(line, sizeof line, &p, 3000, OWL_LINK_BLE, 17940));
    parse_line();
    TEST_ASSERT_TRUE(cJSON_IsTrue(cJSON_GetObjectItem(json, "liked")));
    TEST_ASSERT_TRUE(cJSON_IsNull(cJSON_GetObjectItem(json, "volume")));
    TEST_ASSERT_EQUAL_STRING("ble", str_field("link"));
    TEST_ASSERT_EQUAL_INT64(17940, num_field("wait_s"));
}

static void test_no_device_player_line_is_short(void)
{
    owl_player_t p;
    owl_player_init(&p);
    p.status = OWL_PLAYER_NO_DEVICE;
    TEST_ASSERT_TRUE(owl_shell_player_line(line, sizeof line, &p, 0, OWL_LINK_API, 0));
    parse_line();
    TEST_ASSERT_EQUAL_STRING("no_device", str_field("status"));
    TEST_ASSERT_NULL(str_field("title"));
    TEST_ASSERT_NULL(str_field("device"));
}

static void test_player_line_survives_hostile_metadata(void)
{
    owl_player_t p = playing_track();
    memset(p.track.title, '"', sizeof p.track.title - 1);
    p.track.title[sizeof p.track.title - 1] = '\0';
    memset(p.track.subtitle, '\x01', sizeof p.track.subtitle - 1);
    p.track.subtitle[sizeof p.track.subtitle - 1] = '\0';
    memset(p.track.album, '\\', sizeof p.track.album - 1);
    p.track.album[sizeof p.track.album - 1] = '\0';
    memset(p.device.name, '\x1f', sizeof p.device.name - 1);
    p.device.name[sizeof p.device.name - 1] = '\0';
    TEST_ASSERT_TRUE(owl_shell_player_line(line, sizeof line, &p, 3000, OWL_LINK_API, 0));
    parse_line();
    TEST_ASSERT_EQUAL_STRING("spotify:track:6rqhFgbbKwnb9MLmUQDhG6", str_field("uri"));
    const char *title = str_field("title");
    TEST_ASSERT_TRUE(title == NULL || strlen(title) < 96);
}

static void test_multibyte_titles_are_cut_on_a_character_boundary(void)
{
    owl_player_t p = playing_track();
    p.track.title[0] = '\0';
    for (int i = 0; i < 60; i++) {
        strcat(p.track.title, "\xC3\xA9"); /* e with an acute accent, two bytes */
    }
    TEST_ASSERT_TRUE(owl_shell_player_line(line, sizeof line, &p, 3000, OWL_LINK_API, 0));
    parse_line();
    TEST_ASSERT_TRUE(is_valid_utf8(str_field("title")));
    TEST_ASSERT_EQUAL_size_t(94, strlen(str_field("title"))); /* 95 bytes would split a character */
}

static void test_device_line(void)
{
    owl_list_page_t devices = two_devices();
    TEST_ASSERT_TRUE(owl_shell_device_line(line, sizeof line, 1, &devices.items[0]));
    TEST_ASSERT_EQUAL_STRING("@owl {\"event\":\"device\",\"n\":1,\"id\":\"aaaa1111\",\"name\":\"Pixel 9\","
                             "\"type\":\"Smartphone\",\"active\":true,\"restricted\":false}\n",
                             line);
}

static void test_position_alone_is_not_a_change(void)
{
    owl_player_t a = playing_track();
    owl_player_t b = a;
    b.progress_ms += 4000;
    b.progress_at_ms += 4000;
    TEST_ASSERT_FALSE(owl_shell_player_changed(&a, &b));
    b.device.volume_percent = 30;
    TEST_ASSERT_TRUE(owl_shell_player_changed(&a, &b));
    b = a;
    b.liked_known = true;
    TEST_ASSERT_TRUE(owl_shell_player_changed(&a, &b));
    b = a;
    strcpy(b.track.uri, "spotify:track:other");
    TEST_ASSERT_TRUE(owl_shell_player_changed(&a, &b));
    b = a;
    b.status = OWL_PLAYER_PAUSED;
    TEST_ASSERT_TRUE(owl_shell_player_changed(&a, &b));
}

static void test_help_lists_the_playback_commands(void)
{
    TEST_ASSERT_TRUE(owl_shell_help_line(line, sizeof line));
    parse_line();
    TEST_ASSERT_NOT_NULL(strstr(str_field("commands"), "transfer <n|device id>"));
    TEST_ASSERT_NOT_NULL(strstr(str_field("commands"), "vol <0-100|+n|-n>"));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_empty_lines_are_ignored);
    RUN_TEST(test_commands_are_lowercase_words);
    RUN_TEST(test_an_unexpected_argument_is_refused);
    RUN_TEST(test_cmd_line_is_exact);
    RUN_TEST(test_event_line_is_exact);
    RUN_TEST(test_info_line);
    RUN_TEST(test_info_line_escapes_a_hostile_ssid);
    RUN_TEST(test_help_lists_the_commands);
    RUN_TEST(test_a_buffer_too_small_fails_cleanly);
    RUN_TEST(test_commands_without_arguments);
    RUN_TEST(test_unknown_words_and_extra_arguments);
    RUN_TEST(test_volume_absolute_and_relative);
    RUN_TEST(test_malformed_volumes_are_refused);
    RUN_TEST(test_auth_takes_an_optional_refresh);
    RUN_TEST(test_transfer_takes_a_number_or_a_device_id);
    RUN_TEST(test_playback_verbs_are_marked);
    RUN_TEST(test_toggle_follows_the_player);
    RUN_TEST(test_no_active_device_refuses_playback);
    RUN_TEST(test_volume_is_clamped_and_needs_a_willing_device);
    RUN_TEST(test_like_needs_a_spotify_track);
    RUN_TEST(test_transfer_by_number_or_id);
    RUN_TEST(test_player_line_carries_the_state);
    RUN_TEST(test_no_device_player_line_is_short);
    RUN_TEST(test_player_line_survives_hostile_metadata);
    RUN_TEST(test_multibyte_titles_are_cut_on_a_character_boundary);
    RUN_TEST(test_device_line);
    RUN_TEST(test_position_alone_is_not_a_change);
    RUN_TEST(test_help_lists_the_playback_commands);
    cJSON_Delete(json);
    return UNITY_END();
}
