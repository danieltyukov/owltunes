#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "owl_prov.h"
#include "test_util.h"
#include "unity.h"

#define CLIENT "0123456789abcdef0123456789abcdef"
#define REDIRECT "https://danieltyukov.github.io/owltunes/callback/"
#define STATE "QEFCQ0RFRkdISUpLTE1OTw.192.168.1.23"

static owl_prov_t prov;
static char out[OWL_PROV_LINE_MAX + 64];
static cJSON *reply;
static uint8_t s_next;

static void counting_random(uint8_t *buf, size_t len)
{
    for (size_t i = 0; i < len; i++) {
        buf[i] = s_next++;
    }
}

static void fresh(void)
{
    s_next = 0;
    owl_prov_init(&prov, NULL, "OwlTunes-TEST", "0.2.0", counting_random);
}

/* Send one request at now_ms and parse the response line into reply. */
static void send_at(const char *json, int64_t now_ms)
{
    char line[OWL_PROV_LINE_MAX];
    snprintf(line, sizeof line, "@owl %s", json);
    cJSON_Delete(reply);
    reply = NULL;
    TEST_ASSERT_TRUE(owl_prov_handle_line(&prov, line, now_ms, out, sizeof out));
    TEST_ASSERT_EQUAL_MEMORY(OWL_PROV_PREFIX, out, 5);
    TEST_ASSERT_EQUAL_CHAR('\n', out[strlen(out) - 1]);
    reply = cJSON_Parse(out + 5);
    TEST_ASSERT_NOT_NULL(reply);
}

static void send(const char *json)
{
    send_at(json, 1000);
}

static bool ok(void)
{
    return cJSON_IsTrue(cJSON_GetObjectItem(reply, "ok"));
}

static const char *field(const char *name)
{
    const cJSON *v = cJSON_GetObjectItem(reply, name);
    return cJSON_IsString(v) ? v->valuestring : "";
}

static void expect_error(const char *code)
{
    TEST_ASSERT_FALSE(ok());
    TEST_ASSERT_EQUAL_STRING(code, field("error"));
}

static void linkable(void)
{
    fresh();
    owl_prov_set_network(&prov, true, "192.168.1.23");
    send("{\"id\":1,\"cmd\":\"spotify_client\",\"client_id\":\"" CLIENT "\",\"redirect_uri\":\"" REDIRECT "\"}");
    TEST_ASSERT_TRUE(ok());
    owl_prov_take_actions(&prov);
}

static void test_lines_without_prefix_are_ignored(void)
{
    fresh();
    TEST_ASSERT_FALSE(owl_prov_handle_line(&prov, "I (123) wifi: connected", 0, out, sizeof out));
    TEST_ASSERT_FALSE(owl_prov_handle_line(&prov, "", 0, out, sizeof out));
    TEST_ASSERT_FALSE(owl_prov_handle_line(&prov, "@owlx {}", 0, out, sizeof out));
    TEST_ASSERT_FALSE(owl_prov_handle_line(&prov, "\xff\xfe@owl", 0, out, sizeof out));
}

static void test_malformed_and_unknown_requests(void)
{
    fresh();
    send("{not json");
    expect_error("bad_request");
    send("{\"id\":7,\"cmd\":\"dance\"}");
    expect_error("unknown_cmd");
    TEST_ASSERT_EQUAL_INT(7, cJSON_GetObjectItem(reply, "id")->valueint);
}

static void test_hello_reports_setup_state(void)
{
    fresh();
    send("{\"id\":1,\"cmd\":\"hello\"}");
    TEST_ASSERT_TRUE(ok());
    TEST_ASSERT_EQUAL_STRING("OwlTunes-TEST", field("name"));
    TEST_ASSERT_EQUAL_STRING("0.2.0", field("fw"));
    TEST_ASSERT_EQUAL_STRING("needs_wifi", field("setup"));
    TEST_ASSERT_EQUAL_INT(OWL_PROV_PROTOCOL, cJSON_GetObjectItem(reply, "protocol")->valueint);
    TEST_ASSERT_FALSE(cJSON_IsTrue(cJSON_GetObjectItem(reply, "linked")));
    owl_prov_set_network(&prov, true, "10.0.2.15");
    send("{\"id\":2,\"cmd\":\"hello\"}");
    TEST_ASSERT_EQUAL_STRING("needs_spotify", field("setup"));
    TEST_ASSERT_EQUAL_STRING("10.0.2.15", field("ip"));
}

static void test_wifi_add_validates_saves_and_updates(void)
{
    fresh();
    send("{\"id\":1,\"cmd\":\"wifi_add\",\"ssid\":\"\",\"password\":\"password1\"}");
    expect_error("bad_ssid");
    send("{\"id\":2,\"cmd\":\"wifi_add\",\"ssid\":\"123456789012345678901234567890123\",\"password\":\"\"}");
    expect_error("bad_ssid");
    send("{\"id\":3,\"cmd\":\"wifi_add\",\"ssid\":\"Home\",\"password\":\"short77\"}");
    expect_error("bad_password");
    send("{\"id\":4,\"cmd\":\"wifi_add\",\"ssid\":\"Cafe\",\"password\":\"\"}");
    TEST_ASSERT_TRUE(ok());
    send("{\"id\":5,\"cmd\":\"wifi_add\",\"ssid\":\"Home\",\"password\":\"password1\"}");
    TEST_ASSERT_TRUE(ok());
    TEST_ASSERT_EQUAL_UINT32(OWL_PROV_DO_SAVE | OWL_PROV_DO_JOIN_WIFI, owl_prov_take_actions(&prov));
    send("{\"id\":6,\"cmd\":\"wifi_add\",\"ssid\":\"Home\",\"password\":\"password2\"}");
    TEST_ASSERT_EQUAL_UINT8(2, prov.settings.n_networks);
    TEST_ASSERT_EQUAL_STRING("password2", prov.settings.networks[1].password);
    send("{\"id\":7,\"cmd\":\"wifi_add\",\"ssid\":\"Three\",\"password\":\"password3\"}");
    send("{\"id\":8,\"cmd\":\"wifi_add\",\"ssid\":\"Four\",\"password\":\"password4\"}");
    send("{\"id\":9,\"cmd\":\"wifi_add\",\"ssid\":\"Five\",\"password\":\"password5\"}");
    expect_error("full");
    send("{\"id\":10,\"cmd\":\"hello\"}");
    const cJSON *networks = cJSON_GetObjectItem(reply, "networks");
    TEST_ASSERT_EQUAL_INT(4, cJSON_GetArraySize(networks));
    TEST_ASSERT_EQUAL_STRING("Cafe", cJSON_GetArrayItem(networks, 0)->valuestring);
}

static void test_wifi_remove(void)
{
    fresh();
    send("{\"id\":1,\"cmd\":\"wifi_add\",\"ssid\":\"Home\",\"password\":\"password1\"}");
    send("{\"id\":2,\"cmd\":\"wifi_add\",\"ssid\":\"Hotspot\",\"password\":\"password2\"}");
    send("{\"id\":3,\"cmd\":\"wifi_remove\",\"ssid\":\"Home\"}");
    TEST_ASSERT_TRUE(ok());
    TEST_ASSERT_EQUAL_UINT8(1, prov.settings.n_networks);
    TEST_ASSERT_EQUAL_STRING("Hotspot", prov.settings.networks[0].ssid);
    send("{\"id\":4,\"cmd\":\"wifi_remove\",\"ssid\":\"Home\"}");
    expect_error("not_found");
}

static void test_spotify_client_validates_and_resets_link_on_change(void)
{
    linkable();
    strcpy(prov.settings.refresh_token, "AQOld");
    send("{\"id\":2,\"cmd\":\"spotify_client\",\"client_id\":\"" CLIENT "\",\"redirect_uri\":\"" REDIRECT "\"}");
    TEST_ASSERT_EQUAL_STRING("AQOld", prov.settings.refresh_token);
    send("{\"id\":3,\"cmd\":\"spotify_client\",\"client_id\":\"abc\",\"redirect_uri\":\"" REDIRECT "\"}");
    expect_error("bad_client_id");
    send("{\"id\":4,\"cmd\":\"spotify_client\",\"client_id\":\"" CLIENT "\",\"redirect_uri\":\"http://evil.example/\"}");
    expect_error("bad_redirect_uri");
    send("{\"id\":5,\"cmd\":\"spotify_client\",\"client_id\":\"ffffffffffffffffffffffffffffffff\","
         "\"redirect_uri\":\"" REDIRECT "\"}");
    TEST_ASSERT_TRUE(ok());
    TEST_ASSERT_EQUAL_STRING("", prov.settings.refresh_token);
}

static void test_begin_requires_client(void)
{
    fresh();
    send("{\"id\":1,\"cmd\":\"spotify_begin\"}");
    expect_error("no_client_id");
}

static void test_begin_returns_authorize_url_with_ip_in_state(void)
{
    linkable();
    send("{\"id\":2,\"cmd\":\"spotify_begin\"}");
    TEST_ASSERT_TRUE(ok());
    const char *url = field("authorize_url");
    TEST_ASSERT_EQUAL_MEMORY("https://accounts.spotify.com/authorize?", url, 39);
    TEST_ASSERT_NOT_NULL(strstr(url, "&code_challenge_method=S256&code_challenge="));
    TEST_ASSERT_NOT_NULL(strstr(url, "&state=" STATE));
    TEST_ASSERT_TRUE(strlen(out) <= OWL_PROV_LINE_MAX);
}

static void test_code_flow_exchanges_and_saves_token(void)
{
    linkable();
    send("{\"id\":2,\"cmd\":\"spotify_begin\"}");
    send("{\"id\":3,\"cmd\":\"spotify_code\",\"code\":\"AQDcode-1\",\"state\":\"" STATE "\"}");
    TEST_ASSERT_TRUE(ok());
    TEST_ASSERT_TRUE(cJSON_IsTrue(cJSON_GetObjectItem(reply, "accepted")));
    TEST_ASSERT_EQUAL_UINT32(OWL_PROV_DO_EXCHANGE, owl_prov_take_actions(&prov));
    TEST_ASSERT_EQUAL_STRING("AQDcode-1", prov.code);
    owl_prov_finish_exchange(&prov, true, "AQRefresh");
    TEST_ASSERT_EQUAL_STRING("AQRefresh", prov.settings.refresh_token);
    TEST_ASSERT_EQUAL_UINT32(OWL_PROV_DO_SAVE, owl_prov_take_actions(&prov));
    TEST_ASSERT_EQUAL(OWL_SETUP_STATE_READY, owl_prov_setup_state(&prov));
    TEST_ASSERT_EQUAL_STRING("", prov.code);
    TEST_ASSERT_EQUAL_STRING("no_session", owl_prov_accept_code(&prov, "AQDcode-2", STATE, 2000));
}

static void test_wrong_state_is_rejected(void)
{
    linkable();
    send("{\"id\":2,\"cmd\":\"spotify_begin\"}");
    send("{\"id\":3,\"cmd\":\"spotify_code\",\"code\":\"AQDcode\",\"state\":\"QEFCQ0RFRkdISUpLTE1OTw.192.168.1.99\"}");
    expect_error("bad_state");
    TEST_ASSERT_EQUAL_UINT32(0, owl_prov_take_actions(&prov));
}

static void test_code_without_session_is_rejected(void)
{
    linkable();
    send("{\"id\":2,\"cmd\":\"spotify_code\",\"code\":\"AQDcode\",\"state\":\"" STATE "\"}");
    expect_error("no_session");
}

static void test_expired_session_rejects_code(void)
{
    linkable();
    send_at("{\"id\":2,\"cmd\":\"spotify_begin\"}", 0);
    send_at("{\"id\":3,\"cmd\":\"spotify_code\",\"code\":\"AQDcode\",\"state\":\"" STATE "\"}", OWL_PROV_SESSION_MS);
    expect_error("expired");
    TEST_ASSERT_EQUAL_STRING("no_session", owl_prov_accept_code(&prov, "AQDcode", STATE, OWL_PROV_SESSION_MS + 1));
}

static void test_code_with_unsafe_characters_is_rejected(void)
{
    linkable();
    send("{\"id\":2,\"cmd\":\"spotify_begin\"}");
    send("{\"id\":3,\"cmd\":\"spotify_code\",\"code\":\"AQD&grant_type=x\",\"state\":\"" STATE "\"}");
    expect_error("bad_code");
}

static void test_second_code_while_exchanging_is_busy(void)
{
    linkable();
    send("{\"id\":2,\"cmd\":\"spotify_begin\"}");
    TEST_ASSERT_NULL(owl_prov_accept_code(&prov, "AQDone", STATE, 1000));
    TEST_ASSERT_EQUAL_STRING("busy", owl_prov_accept_code(&prov, "AQDtwo", STATE, 1000));
}

static void test_failed_exchange_ends_session(void)
{
    linkable();
    send("{\"id\":2,\"cmd\":\"spotify_begin\"}");
    owl_prov_accept_code(&prov, "AQDone", STATE, 1000);
    owl_prov_take_actions(&prov);
    owl_prov_finish_exchange(&prov, false, NULL);
    TEST_ASSERT_EQUAL_STRING("", prov.settings.refresh_token);
    TEST_ASSERT_EQUAL_UINT32(0, owl_prov_take_actions(&prov));
    TEST_ASSERT_EQUAL_STRING("no_session", owl_prov_accept_code(&prov, "AQDtwo", STATE, 1000));
}

static void test_logout_clears_token(void)
{
    linkable();
    strcpy(prov.settings.refresh_token, "AQRefresh");
    send("{\"id\":2,\"cmd\":\"spotify_logout\"}");
    TEST_ASSERT_TRUE(ok());
    TEST_ASSERT_EQUAL_STRING("", prov.settings.refresh_token);
    TEST_ASSERT_EQUAL_UINT32(OWL_PROV_DO_SAVE, owl_prov_take_actions(&prov));
}

static void test_refresh_rotation_saves_new_token(void)
{
    linkable();
    strcpy(prov.settings.refresh_token, "AQOld");
    TEST_ASSERT_FALSE(owl_prov_apply_refresh(&prov, SPOTIFY_TOKEN_OK, "AQOld"));
    TEST_ASSERT_EQUAL_UINT32(0, owl_prov_take_actions(&prov));
    TEST_ASSERT_FALSE(owl_prov_apply_refresh(&prov, SPOTIFY_TOKEN_OK, "AQNew"));
    TEST_ASSERT_EQUAL_STRING("AQNew", prov.settings.refresh_token);
    TEST_ASSERT_EQUAL_UINT32(OWL_PROV_DO_SAVE, owl_prov_take_actions(&prov));
}

static void test_refresh_rejection_forgets_login(void)
{
    linkable();
    strcpy(prov.settings.refresh_token, "AQOld");
    TEST_ASSERT_TRUE(owl_prov_apply_refresh(&prov, SPOTIFY_TOKEN_LOG_IN_AGAIN, NULL));
    TEST_ASSERT_EQUAL_STRING("", prov.settings.refresh_token);
    TEST_ASSERT_EQUAL_UINT32(OWL_PROV_DO_SAVE, owl_prov_take_actions(&prov));
    TEST_ASSERT_EQUAL(OWL_SETUP_STATE_NEEDS_SPOTIFY, owl_prov_setup_state(&prov));
    strcpy(prov.settings.refresh_token, "AQOld");
    TEST_ASSERT_TRUE(owl_prov_apply_refresh(&prov, SPOTIFY_TOKEN_BAD_CLIENT, NULL));
    TEST_ASSERT_EQUAL_STRING("", prov.settings.refresh_token);
}

static void test_refresh_retry_keeps_login(void)
{
    linkable();
    strcpy(prov.settings.refresh_token, "AQOld");
    TEST_ASSERT_FALSE(owl_prov_apply_refresh(&prov, SPOTIFY_TOKEN_RETRY, NULL));
    TEST_ASSERT_FALSE(owl_prov_apply_refresh(&prov, SPOTIFY_TOKEN_BAD_RESPONSE, NULL));
    TEST_ASSERT_EQUAL_STRING("AQOld", prov.settings.refresh_token);
    TEST_ASSERT_EQUAL_UINT32(0, owl_prov_take_actions(&prov));
}

static void test_settings_from_another_version_fall_back_to_defaults(void)
{
    owl_settings_t saved;
    owl_settings_defaults(&saved);
    strcpy(saved.client_id, CLIENT);
    saved.version = OWL_SETTINGS_VERSION + 1;
    owl_prov_init(&prov, &saved, "OwlTunes-TEST", "0.2.0", counting_random);
    TEST_ASSERT_EQUAL_STRING("", prov.settings.client_id);
    saved.version = OWL_SETTINGS_VERSION;
    owl_prov_init(&prov, &saved, "OwlTunes-TEST", "0.2.0", counting_random);
    TEST_ASSERT_EQUAL_STRING(CLIENT, prov.settings.client_id);
}

static void test_event_lines(void)
{
    TEST_ASSERT_TRUE(owl_prov_event(out, sizeof out, "spotify", "failed", "error", "invalid_client"));
    TEST_ASSERT_EQUAL_STRING("@owl {\"event\":\"spotify\",\"state\":\"failed\",\"error\":\"invalid_client\"}\n", out);
    TEST_ASSERT_TRUE(owl_prov_event(out, sizeof out, "spotify", "linked", NULL, NULL));
    TEST_ASSERT_EQUAL_STRING("@owl {\"event\":\"spotify\",\"state\":\"linked\"}\n", out);
    TEST_ASSERT_FALSE(owl_prov_event(out, 10, "spotify", "linked", NULL, NULL));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_lines_without_prefix_are_ignored);
    RUN_TEST(test_malformed_and_unknown_requests);
    RUN_TEST(test_hello_reports_setup_state);
    RUN_TEST(test_wifi_add_validates_saves_and_updates);
    RUN_TEST(test_wifi_remove);
    RUN_TEST(test_spotify_client_validates_and_resets_link_on_change);
    RUN_TEST(test_begin_requires_client);
    RUN_TEST(test_begin_returns_authorize_url_with_ip_in_state);
    RUN_TEST(test_code_flow_exchanges_and_saves_token);
    RUN_TEST(test_wrong_state_is_rejected);
    RUN_TEST(test_code_without_session_is_rejected);
    RUN_TEST(test_expired_session_rejects_code);
    RUN_TEST(test_code_with_unsafe_characters_is_rejected);
    RUN_TEST(test_second_code_while_exchanging_is_busy);
    RUN_TEST(test_failed_exchange_ends_session);
    RUN_TEST(test_logout_clears_token);
    RUN_TEST(test_refresh_rotation_saves_new_token);
    RUN_TEST(test_refresh_rejection_forgets_login);
    RUN_TEST(test_refresh_retry_keeps_login);
    RUN_TEST(test_settings_from_another_version_fall_back_to_defaults);
    RUN_TEST(test_event_lines);
    cJSON_Delete(reply);
    return UNITY_END();
}
