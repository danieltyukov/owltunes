#include <string.h>

#include "owl_text.h"
#include "test_util.h"
#include "unity.h"

static void test_utf8_copy_fits(void)
{
    char buf[16];
    TEST_ASSERT_EQUAL_UINT(5, owl_utf8_copy(buf, sizeof buf, "hello"));
    TEST_ASSERT_EQUAL_STRING("hello", buf);
}

static void test_utf8_copy_null_src_gives_empty_string(void)
{
    char buf[4] = "xyz";
    TEST_ASSERT_EQUAL_UINT(0, owl_utf8_copy(buf, sizeof buf, NULL));
    TEST_ASSERT_EQUAL_STRING("", buf);
}

static void test_utf8_copy_truncates_ascii(void)
{
    char buf[4];
    TEST_ASSERT_EQUAL_UINT(3, owl_utf8_copy(buf, sizeof buf, "abcdef"));
    TEST_ASSERT_EQUAL_STRING("abc", buf);
}

static void test_utf8_copy_never_splits_multibyte(void)
{
    /* "a", U+00E9 (2 bytes), U+1F989 owl (4 bytes). Five usable bytes hold "a" and U+00E9 only. */
    char buf[6];
    TEST_ASSERT_EQUAL_UINT(3, owl_utf8_copy(buf, sizeof buf, "a\xC3\xA9\xF0\x9F\xA6\x89"));
    TEST_ASSERT_EQUAL_STRING("a\xC3\xA9", buf);
    TEST_ASSERT_TRUE(is_valid_utf8(buf));
}

static void test_utf8_copy_cuts_cjk_on_boundary(void)
{
    char buf[5]; /* two 3-byte characters do not fit in 4 bytes */
    TEST_ASSERT_EQUAL_UINT(3, owl_utf8_copy(buf, sizeof buf, "\xE6\x97\xA5\xE6\x9C\xAC"));
    TEST_ASSERT_EQUAL_STRING("\xE6\x97\xA5", buf);
}

static void test_utf8_append_joins_and_truncates(void)
{
    char buf[10] = "Owls";
    TEST_ASSERT_EQUAL_UINT(6, owl_utf8_append(buf, sizeof buf, ", "));
    TEST_ASSERT_EQUAL_UINT(9, owl_utf8_append(buf, sizeof buf, "Moonlight"));
    TEST_ASSERT_EQUAL_STRING("Owls, Moo", buf);
    TEST_ASSERT_EQUAL_UINT(9, owl_utf8_append(buf, sizeof buf, "more"));
}

static void test_url_encode_spotify_uri(void)
{
    char buf[64];
    size_t n = owl_url_encode(buf, sizeof buf, "spotify:track:6rqhFgbbKwnb9MLmUQDhG6");
    TEST_ASSERT_EQUAL_STRING("spotify%3Atrack%3A6rqhFgbbKwnb9MLmUQDhG6", buf);
    TEST_ASSERT_EQUAL_UINT(strlen(buf), n);
}

static void test_url_encode_overflow_returns_marker(void)
{
    char buf[4];
    TEST_ASSERT_EQUAL(OWL_TEXT_OVERFLOW, owl_url_encode(buf, sizeof buf, "a:b"));
    TEST_ASSERT_EQUAL_STRING("", buf);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_utf8_copy_fits);
    RUN_TEST(test_utf8_copy_null_src_gives_empty_string);
    RUN_TEST(test_utf8_copy_truncates_ascii);
    RUN_TEST(test_utf8_copy_never_splits_multibyte);
    RUN_TEST(test_utf8_copy_cuts_cjk_on_boundary);
    RUN_TEST(test_utf8_append_joins_and_truncates);
    RUN_TEST(test_url_encode_spotify_uri);
    RUN_TEST(test_url_encode_overflow_returns_marker);
    return UNITY_END();
}
