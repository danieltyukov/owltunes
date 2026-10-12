#include <stdlib.h>
#include <string.h>

#include "spotify_api.h"
#include "spotify_parse.h"
#include "test_util.h"
#include "unity.h"

static void test_liked_request_asks_about_one_uri(void)
{
    spotify_request_t req;
    TEST_ASSERT_TRUE(spotify_request_liked("spotify:track:6rqhFgbbKwnb9MLmUQDhG6", &req));
    TEST_ASSERT_EQUAL(SPOTIFY_GET, req.method);
    TEST_ASSERT_EQUAL_STRING("/v1/me/library/contains?uris=spotify%3Atrack%3A6rqhFgbbKwnb9MLmUQDhG6",
                             req.path);
    TEST_ASSERT_EQUAL_STRING("", req.body);
}

static void test_liked_request_refuses_unsafe_uris(void)
{
    spotify_request_t req;
    TEST_ASSERT_FALSE(spotify_request_liked("spotify:track:a&uris=b", &req));
    TEST_ASSERT_FALSE(spotify_request_liked("", &req));
    TEST_ASSERT_FALSE(spotify_request_liked(NULL, &req));
}

static void test_recorded_answer_says_liked(void)
{
    size_t len;
    char *json = read_fixture("library_contains.json", &len);
    bool liked = false;
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, spotify_parse_liked(json, len, &liked));
    TEST_ASSERT_TRUE(liked);
    free(json);
}

static void test_false_means_not_liked(void)
{
    bool liked = true;
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_OK, spotify_parse_liked("[false]", 7, &liked));
    TEST_ASSERT_FALSE(liked);
}

static void test_unexpected_answers_leave_the_state_alone(void)
{
    bool liked = true;
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_SHAPE, spotify_parse_liked("[]", 2, &liked));
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_SHAPE, spotify_parse_liked("{\"liked\":true}", 14, &liked));
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_SHAPE, spotify_parse_liked("[\"true\"]", 8, &liked));
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_SHAPE, spotify_parse_liked("", 0, &liked));
    TEST_ASSERT_EQUAL(SPOTIFY_PARSE_BAD_JSON, spotify_parse_liked("[tru", 4, &liked));
    TEST_ASSERT_TRUE(liked);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_liked_request_asks_about_one_uri);
    RUN_TEST(test_liked_request_refuses_unsafe_uris);
    RUN_TEST(test_recorded_answer_says_liked);
    RUN_TEST(test_false_means_not_liked);
    RUN_TEST(test_unexpected_answers_leave_the_state_alone);
    return UNITY_END();
}
