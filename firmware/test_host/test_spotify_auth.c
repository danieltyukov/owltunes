#include <string.h>

#include "spotify_auth.h"
#include "test_util.h"
#include "unity.h"

#define CLIENT "0123456789abcdef0123456789abcdef"
#define REDIRECT "https://danieltyukov.github.io/owltunes/callback/"
#define VERIFIER_0_63 "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8gISIjJCUmJygpKissLS4vMDEyMzQ1Njc4OTo7PD0-Pw"

static uint8_t s_next;

/* Deterministic stand-in for the hardware RNG: 0, 1, 2, ... */
static void counting_random(uint8_t *buf, size_t len)
{
    for (size_t i = 0; i < len; i++) {
        buf[i] = s_next++;
    }
}

static void test_client_id_validation(void)
{
    TEST_ASSERT_TRUE(spotify_client_id_valid(CLIENT));
    TEST_ASSERT_FALSE(spotify_client_id_valid("0123456789ABCDEF0123456789ABCDEF"));
    TEST_ASSERT_FALSE(spotify_client_id_valid("0123456789abcdef"));
    TEST_ASSERT_FALSE(spotify_client_id_valid("0123456789abcdef0123456789abcdeg"));
    TEST_ASSERT_FALSE(spotify_client_id_valid(NULL));
}

static void test_redirect_uri_validation(void)
{
    TEST_ASSERT_TRUE(spotify_redirect_uri_valid(REDIRECT));
    TEST_ASSERT_TRUE(spotify_redirect_uri_valid("http://127.0.0.1:4173/owltunes/callback/"));
    TEST_ASSERT_FALSE(spotify_redirect_uri_valid("http://example.com/callback/"));
    TEST_ASSERT_FALSE(spotify_redirect_uri_valid("javascript:alert(1)"));
    TEST_ASSERT_FALSE(spotify_redirect_uri_valid("https://example.com/a b"));
    TEST_ASSERT_FALSE(spotify_redirect_uri_valid("https://example.com/\"x"));
    char long_uri[200];
    memset(long_uri, 'a', sizeof long_uri - 1);
    memcpy(long_uri, "https://", 8);
    long_uri[sizeof long_uri - 1] = '\0';
    TEST_ASSERT_FALSE(spotify_redirect_uri_valid(long_uri));
}

static void test_code_validation(void)
{
    TEST_ASSERT_TRUE(spotify_code_valid("AQDx-y_z.0~9"));
    TEST_ASSERT_FALSE(spotify_code_valid(""));
    TEST_ASSERT_FALSE(spotify_code_valid("abc&state=x"));
    TEST_ASSERT_FALSE(spotify_code_valid("abc\"def"));
    char long_code[SPOTIFY_CODE_LEN + 1];
    memset(long_code, 'A', SPOTIFY_CODE_LEN);
    long_code[SPOTIFY_CODE_LEN] = '\0';
    TEST_ASSERT_FALSE(spotify_code_valid(long_code));
}

static void test_pkce_from_random_bytes(void)
{
    spotify_pkce_t s;
    s_next = 0;
    spotify_pkce_new(&s, counting_random, "192.168.1.23");
    TEST_ASSERT_EQUAL_STRING(VERIFIER_0_63, s.verifier);
    TEST_ASSERT_EQUAL_STRING("wsNdZaf3VpLTsEDmR5gPk2C6xYVWxKb0xcaG3O6kX10", s.challenge);
    TEST_ASSERT_EQUAL_STRING("QEFCQ0RFRkdISUpLTE1OTw.192.168.1.23", s.state);
}

static void test_pkce_without_ip_has_bare_nonce(void)
{
    spotify_pkce_t s;
    s_next = 0;
    spotify_pkce_new(&s, counting_random, NULL);
    TEST_ASSERT_EQUAL_STRING("QEFCQ0RFRkdISUpLTE1OTw", s.state);
    s_next = 0;
    spotify_pkce_new(&s, counting_random, "not-an-ip");
    TEST_ASSERT_EQUAL_STRING("QEFCQ0RFRkdISUpLTE1OTw", s.state);
}

static void test_state_matching(void)
{
    spotify_pkce_t s;
    s_next = 0;
    spotify_pkce_new(&s, counting_random, "10.0.0.5");
    TEST_ASSERT_TRUE(spotify_state_matches(&s, "QEFCQ0RFRkdISUpLTE1OTw.10.0.0.5"));
    TEST_ASSERT_FALSE(spotify_state_matches(&s, "QEFCQ0RFRkdISUpLTE1OTw.10.0.0.6"));
    TEST_ASSERT_FALSE(spotify_state_matches(&s, NULL));
}

static void test_authorize_url(void)
{
    spotify_pkce_t s;
    char url[768];
    s_next = 0;
    spotify_pkce_new(&s, counting_random, "192.168.1.23");
    TEST_ASSERT_TRUE(spotify_authorize_url(CLIENT, REDIRECT, &s, url, sizeof url));
    TEST_ASSERT_EQUAL_STRING(
        "https://accounts.spotify.com/authorize?response_type=code&client_id=" CLIENT
        "&scope=user-read-playback-state%20user-modify-playback-state%20user-read-currently-playing%20"
        "user-library-read%20user-library-modify%20playlist-read-private%20playlist-read-collaborative%20"
        "user-read-recently-played"
        "&redirect_uri=https%3A%2F%2Fdanieltyukov.github.io%2Fowltunes%2Fcallback%2F"
        "&code_challenge_method=S256&code_challenge=wsNdZaf3VpLTsEDmR5gPk2C6xYVWxKb0xcaG3O6kX10"
        "&state=QEFCQ0RFRkdISUpLTE1OTw.192.168.1.23",
        url);
    TEST_ASSERT_FALSE(spotify_authorize_url("bad", REDIRECT, &s, url, sizeof url));
    TEST_ASSERT_FALSE(spotify_authorize_url(CLIENT, REDIRECT, &s, url, 64));
}

static void test_token_bodies(void)
{
    char body[1024];
    TEST_ASSERT_TRUE(spotify_token_body_for_code(CLIENT, REDIRECT, "AQDcode", VERIFIER_0_63, body, sizeof body));
    TEST_ASSERT_EQUAL_STRING("grant_type=authorization_code&code=AQDcode"
                             "&redirect_uri=https%3A%2F%2Fdanieltyukov.github.io%2Fowltunes%2Fcallback%2F"
                             "&client_id=" CLIENT "&code_verifier=" VERIFIER_0_63,
                             body);
    TEST_ASSERT_FALSE(spotify_token_body_for_code(CLIENT, REDIRECT, "bad&code", VERIFIER_0_63, body, sizeof body));
    TEST_ASSERT_TRUE(spotify_token_body_for_refresh(CLIENT, "AQB/refresh+token", body, sizeof body));
    TEST_ASSERT_EQUAL_STRING("grant_type=refresh_token&refresh_token=AQB%2Frefresh%2Btoken&client_id=" CLIENT, body);
}

static spotify_token_t token;
static char error[64];

static spotify_token_result_t parse(int status, const char *body)
{
    return spotify_parse_token_response(status, body, strlen(body), 1000, &token, error, sizeof error);
}

static void test_successful_exchange_stores_tokens(void)
{
    memset(&token, 0, sizeof token);
    TEST_ASSERT_EQUAL(SPOTIFY_TOKEN_OK,
                      parse(200, "{\"access_token\":\"BQAccess\",\"token_type\":\"Bearer\",\"expires_in\":3600,"
                                 "\"refresh_token\":\"AQRefresh1\",\"scope\":\"user-read-playback-state\"}"));
    TEST_ASSERT_EQUAL_STRING("BQAccess", token.access_token);
    TEST_ASSERT_EQUAL_STRING("AQRefresh1", token.refresh_token);
    TEST_ASSERT_EQUAL_INT64(1000 + 3600000, token.expires_at_ms);
    TEST_ASSERT_EQUAL_STRING("", error);
}

static void test_refresh_without_new_token_keeps_old_one(void)
{
    memset(&token, 0, sizeof token);
    strcpy(token.refresh_token, "AQRefresh1");
    TEST_ASSERT_EQUAL(SPOTIFY_TOKEN_OK, parse(200, "{\"access_token\":\"BQNew\",\"expires_in\":3600}"));
    TEST_ASSERT_EQUAL_STRING("BQNew", token.access_token);
    TEST_ASSERT_EQUAL_STRING("AQRefresh1", token.refresh_token);
}

static void test_invalid_grant_means_log_in_again(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_TOKEN_LOG_IN_AGAIN,
                      parse(400, "{\"error\":\"invalid_grant\",\"error_description\":\"Refresh token revoked\"}"));
    TEST_ASSERT_EQUAL_STRING("invalid_grant", error);
}

static void test_invalid_client_is_a_setup_problem(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_TOKEN_BAD_CLIENT,
                      parse(400, "{\"error\":\"invalid_client\",\"error_description\":\"Invalid client\"}"));
    TEST_ASSERT_EQUAL_STRING("invalid_client", error);
}

static void test_server_error_is_retryable(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_TOKEN_RETRY, parse(503, "<html>Service Unavailable</html>"));
    TEST_ASSERT_EQUAL(SPOTIFY_TOKEN_RETRY, parse(429, ""));
}

static void test_success_without_access_token_is_bad(void)
{
    TEST_ASSERT_EQUAL(SPOTIFY_TOKEN_BAD_RESPONSE, parse(200, "{\"token_type\":\"Bearer\"}"));
    TEST_ASSERT_EQUAL(SPOTIFY_TOKEN_BAD_RESPONSE, parse(200, "not json"));
}

static void test_needs_refresh(void)
{
    spotify_token_t t;
    memset(&t, 0, sizeof t);
    TEST_ASSERT_TRUE(spotify_token_needs_refresh(&t, 0));
    strcpy(t.access_token, "BQ");
    t.expires_at_ms = 100000;
    TEST_ASSERT_FALSE(spotify_token_needs_refresh(&t, 100000 - SPOTIFY_REFRESH_MARGIN_MS - 1));
    TEST_ASSERT_TRUE(spotify_token_needs_refresh(&t, 100000 - SPOTIFY_REFRESH_MARGIN_MS));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_client_id_validation);
    RUN_TEST(test_redirect_uri_validation);
    RUN_TEST(test_code_validation);
    RUN_TEST(test_pkce_from_random_bytes);
    RUN_TEST(test_pkce_without_ip_has_bare_nonce);
    RUN_TEST(test_state_matching);
    RUN_TEST(test_authorize_url);
    RUN_TEST(test_token_bodies);
    RUN_TEST(test_successful_exchange_stores_tokens);
    RUN_TEST(test_refresh_without_new_token_keeps_old_one);
    RUN_TEST(test_invalid_grant_means_log_in_again);
    RUN_TEST(test_invalid_client_is_a_setup_problem);
    RUN_TEST(test_server_error_is_retryable);
    RUN_TEST(test_success_without_access_token_is_bad);
    RUN_TEST(test_needs_refresh);
    return UNITY_END();
}
