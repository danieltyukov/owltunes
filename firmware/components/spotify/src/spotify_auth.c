#include "spotify_auth.h"

#include <stdio.h>
#include <string.h>

#include "owl_text.h"
#include "spotify_json.h"

bool spotify_client_id_valid(const char *s)
{
    if (s == NULL || strlen(s) != 32) {
        return false;
    }
    for (; *s; s++) {
        if (!((*s >= '0' && *s <= '9') || (*s >= 'a' && *s <= 'f'))) {
            return false;
        }
    }
    return true;
}

bool spotify_redirect_uri_valid(const char *s)
{
    if (s == NULL || strlen(s) >= SPOTIFY_REDIRECT_URI_LEN) {
        return false;
    }
    if (strncmp(s, "https://", 8) != 0 && strncmp(s, "http://127.0.0.1:", 17) != 0) {
        return false;
    }
    for (; *s; s++) {
        if (*s <= ' ' || *s > '~' || *s == '"' || *s == '\'' || *s == '<' || *s == '>' || *s == '\\') {
            return false;
        }
    }
    return true;
}

bool spotify_code_valid(const char *s)
{
    if (s == NULL || s[0] == '\0' || strlen(s) >= SPOTIFY_CODE_LEN) {
        return false;
    }
    for (; *s; s++) {
        if (!owl_url_unreserved((unsigned char)*s)) {
            return false;
        }
    }
    return true;
}

static bool ipv4_text(const char *s)
{
    size_t len = s ? strlen(s) : 0;
    if (len < 7 || len > 15) {
        return false;
    }
    for (; *s; s++) {
        if (!((*s >= '0' && *s <= '9') || *s == '.')) {
            return false;
        }
    }
    return true;
}

void spotify_pkce_new(spotify_pkce_t *s, owl_random_fn random, const char *lan_ip)
{
    uint8_t bytes[64];
    uint8_t digest[32];
    memset(s, 0, sizeof *s);
    random(bytes, sizeof bytes);
    owl_base64url(s->verifier, sizeof s->verifier, bytes, sizeof bytes);
    owl_sha256((const uint8_t *)s->verifier, strlen(s->verifier), digest);
    owl_base64url(s->challenge, sizeof s->challenge, digest, sizeof digest);
    random(bytes, 16);
    owl_base64url(s->state, sizeof s->state, bytes, 16);
    if (ipv4_text(lan_ip)) {
        owl_utf8_append(s->state, sizeof s->state, ".");
        owl_utf8_append(s->state, sizeof s->state, lan_ip);
    }
    memset(bytes, 0, sizeof bytes);
}

bool spotify_state_matches(const spotify_pkce_t *s, const char *state)
{
    return s->state[0] != '\0' && owl_ct_streq(s->state, state);
}

/* URL-encode src into dst; false when it does not fit. */
static bool encode(char *dst, size_t cap, const char *src)
{
    return owl_url_encode(dst, cap, src) != OWL_TEXT_OVERFLOW;
}

static bool fits(int n, size_t cap)
{
    return n > 0 && (size_t)n < cap;
}

bool spotify_authorize_url(const char *client_id, const char *redirect_uri, const spotify_pkce_t *s,
                           char *out, size_t cap)
{
    char scope[256], redirect[3 * SPOTIFY_REDIRECT_URI_LEN], state[3 * SPOTIFY_STATE_LEN];
    if (!spotify_client_id_valid(client_id) || !spotify_redirect_uri_valid(redirect_uri) ||
        !encode(scope, sizeof scope, SPOTIFY_SCOPES) || !encode(redirect, sizeof redirect, redirect_uri) ||
        !encode(state, sizeof state, s->state)) {
        return false;
    }
    int n = snprintf(out, cap,
                     SPOTIFY_AUTHORIZE_URL "?response_type=code&client_id=%s&scope=%s&redirect_uri=%s"
                                           "&code_challenge_method=S256&code_challenge=%s&state=%s",
                     client_id, scope, redirect, s->challenge, state);
    return fits(n, cap);
}

bool spotify_token_body_for_code(const char *client_id, const char *redirect_uri, const char *code,
                                 const char *verifier, char *out, size_t cap)
{
    char redirect[3 * SPOTIFY_REDIRECT_URI_LEN];
    if (!spotify_client_id_valid(client_id) || !spotify_redirect_uri_valid(redirect_uri) ||
        !spotify_code_valid(code) || !encode(redirect, sizeof redirect, redirect_uri)) {
        return false;
    }
    int n = snprintf(out, cap,
                     "grant_type=authorization_code&code=%s&redirect_uri=%s&client_id=%s&code_verifier=%s",
                     code, redirect, client_id, verifier);
    return fits(n, cap);
}

bool spotify_token_body_for_refresh(const char *client_id, const char *refresh_token, char *out, size_t cap)
{
    char refresh[3 * SPOTIFY_REFRESH_TOKEN_LEN];
    if (!spotify_client_id_valid(client_id) || refresh_token == NULL || refresh_token[0] == '\0' ||
        !encode(refresh, sizeof refresh, refresh_token)) {
        return false;
    }
    int n = snprintf(out, cap, "grant_type=refresh_token&refresh_token=%s&client_id=%s", refresh, client_id);
    return fits(n, cap);
}

spotify_token_result_t spotify_parse_token_response(int http_status, const char *body, size_t len,
                                                    int64_t now_ms, spotify_token_t *token, char *error,
                                                    size_t error_cap)
{
    owl_utf8_copy(error, error_cap, "");
    if (http_status == 429 || http_status >= 500) {
        return SPOTIFY_TOKEN_RETRY;
    }
    cJSON *root = (body != NULL && len > 0) ? cJSON_ParseWithLength(body, len) : NULL;
    spotify_token_result_t result = SPOTIFY_TOKEN_BAD_RESPONSE;
    if (http_status == 200) {
        const char *access = root ? sj_str(root, "access_token") : NULL;
        if (access != NULL && access[0] != '\0' && strlen(access) < sizeof token->access_token) {
            const char *refresh = sj_str(root, "refresh_token");
            int64_t expires_in = sj_int(root, "expires_in", 3600);
            if (expires_in > SPOTIFY_TOKEN_LIFETIME_MAX_S) {
                expires_in = SPOTIFY_TOKEN_LIFETIME_MAX_S; /* refresh at least once a day */
            }
            owl_utf8_copy(token->access_token, sizeof token->access_token, access);
            if (refresh != NULL && refresh[0] != '\0' && strlen(refresh) < sizeof token->refresh_token) {
                owl_utf8_copy(token->refresh_token, sizeof token->refresh_token, refresh);
            }
            token->expires_at_ms = now_ms + (expires_in > 0 ? expires_in : 3600) * 1000;
            result = SPOTIFY_TOKEN_OK;
        }
    } else {
        const char *code = root ? sj_str(root, "error") : NULL;
        owl_utf8_copy(error, error_cap, code);
        if (code != NULL && strcmp(code, "invalid_grant") == 0) {
            result = SPOTIFY_TOKEN_LOG_IN_AGAIN;
        } else if (http_status == 401 || (code != NULL && (strcmp(code, "invalid_client") == 0 ||
                                                           strcmp(code, "unauthorized_client") == 0))) {
            result = SPOTIFY_TOKEN_BAD_CLIENT;
        }
    }
    cJSON_Delete(root);
    return result;
}

bool spotify_token_needs_refresh(const spotify_token_t *t, int64_t now_ms)
{
    return t->access_token[0] == '\0' || now_ms >= t->expires_at_ms - SPOTIFY_REFRESH_MARGIN_MS;
}
