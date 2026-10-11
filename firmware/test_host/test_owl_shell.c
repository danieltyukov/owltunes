#include <string.h>

#include "cJSON.h"
#include "owl_shell.h"
#include "test_util.h"
#include "unity.h"

static owl_shell_cmd_t cmd;
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
    cJSON_Delete(json);
    return UNITY_END();
}
