#include <string.h>

#include "owl_line.h"
#include "unity.h"

static owl_line_t lines;
static char got[8][OWL_PROV_LINE_MAX];
static int n_got;

static void collect(const char *line, void *ctx)
{
    (void)ctx;
    if (n_got < 8) {
        strcpy(got[n_got], line);
    }
    n_got++;
}

static void reset(void)
{
    owl_line_init(&lines);
    n_got = 0;
}

static void feed(const char *s)
{
    owl_line_feed(&lines, s, strlen(s), collect, NULL);
}

/* A line can hold a Wi-Fi password or a login code: nothing of it stays in the buffer once handled. */
static void test_a_delivered_line_is_wiped_from_the_buffer(void)
{
    reset();
    feed("@owl {\"cmd\":\"wifi_add\",\"password\":\"hunter2hunter2\"}\n");
    TEST_ASSERT_EQUAL(1, n_got);
    for (size_t i = 0; i < sizeof lines.buf; i++) {
        TEST_ASSERT_EQUAL_CHAR(0, lines.buf[i]);
    }
}

static void test_a_bare_carriage_return_ends_a_line(void)
{
    reset();
    feed("info\rhelp\r");
    TEST_ASSERT_EQUAL(2, n_got);
    TEST_ASSERT_EQUAL_STRING("info", got[0]);
    TEST_ASSERT_EQUAL_STRING("help", got[1]);
}

static void test_chunks_are_reassembled(void)
{
    reset();
    feed("@owl {\"id\"");
    feed(":1}\n@owl {\"i");
    TEST_ASSERT_EQUAL_INT(1, n_got);
    TEST_ASSERT_EQUAL_STRING("@owl {\"id\":1}", got[0]);
    feed("d\":2}\n");
    TEST_ASSERT_EQUAL_INT(2, n_got);
    TEST_ASSERT_EQUAL_STRING("@owl {\"id\":2}", got[1]);
}

static void test_crlf_and_empty_lines(void)
{
    reset();
    feed("\r\n\n@owl {}\r\nI (12) log\n");
    TEST_ASSERT_EQUAL_INT(2, n_got);
    TEST_ASSERT_EQUAL_STRING("@owl {}", got[0]);
    TEST_ASSERT_EQUAL_STRING("I (12) log", got[1]);
}

static void test_longest_line_fits(void)
{
    static char line[OWL_PROV_LINE_MAX + 1];
    reset();
    memset(line, 'y', OWL_PROV_LINE_MAX - 1);
    line[OWL_PROV_LINE_MAX - 1] = '\n';
    line[OWL_PROV_LINE_MAX] = '\0';
    feed(line);
    TEST_ASSERT_EQUAL_INT(1, n_got);
    TEST_ASSERT_EQUAL_size_t(OWL_PROV_LINE_MAX - 1, strlen(got[0]));
}

static void test_overlong_line_is_dropped_whole(void)
{
    static char big[OWL_PROV_LINE_MAX + 1];
    reset();
    memset(big, 'x', OWL_PROV_LINE_MAX);
    big[OWL_PROV_LINE_MAX] = '\0';
    feed(big);
    feed("tail\n@owl {}\n");
    TEST_ASSERT_EQUAL_INT(1, n_got);
    TEST_ASSERT_EQUAL_STRING("@owl {}", got[0]);
}

static void test_nul_byte_drops_the_line(void)
{
    reset();
    owl_line_feed(&lines, "@owl {\0}\n@owl {}\n", 17, collect, NULL);
    TEST_ASSERT_EQUAL_INT(1, n_got);
    TEST_ASSERT_EQUAL_STRING("@owl {}", got[0]);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_chunks_are_reassembled);
    RUN_TEST(test_crlf_and_empty_lines);
    RUN_TEST(test_a_delivered_line_is_wiped_from_the_buffer);
    RUN_TEST(test_a_bare_carriage_return_ends_a_line);
    RUN_TEST(test_longest_line_fits);
    RUN_TEST(test_overlong_line_is_dropped_whole);
    RUN_TEST(test_nul_byte_drops_the_line);
    return UNITY_END();
}
