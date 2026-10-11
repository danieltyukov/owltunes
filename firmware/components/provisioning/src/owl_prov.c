#include "owl_prov.h"

#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "owl_text.h"

void owl_settings_defaults(owl_settings_t *s)
{
    memset(s, 0, sizeof *s);
    s->version = OWL_SETTINGS_VERSION;
}

void owl_prov_init(owl_prov_t *p, const owl_settings_t *saved, const char *name, const char *fw,
                   owl_random_fn random)
{
    memset(p, 0, sizeof *p);
    if (saved != NULL && saved->version == OWL_SETTINGS_VERSION &&
        saved->n_networks <= OWL_PROV_MAX_NETWORKS) {
        p->settings = *saved;
    } else {
        owl_settings_defaults(&p->settings);
    }
    owl_utf8_copy(p->name, sizeof p->name, name);
    owl_utf8_copy(p->fw, sizeof p->fw, fw);
    p->random = random;
}

void owl_prov_set_network(owl_prov_t *p, bool up, const char *ip)
{
    p->network_up = up;
    owl_utf8_copy(p->ip, sizeof p->ip, up ? ip : NULL);
}

owl_setup_state_t owl_prov_setup_state(const owl_prov_t *p)
{
    if (p->settings.refresh_token[0] != '\0') {
        return OWL_SETUP_STATE_READY;
    }
    return p->network_up ? OWL_SETUP_STATE_NEEDS_SPOTIFY : OWL_SETUP_STATE_NEEDS_WIFI;
}

const char *owl_prov_setup_state_name(owl_setup_state_t s)
{
    switch (s) {
    case OWL_SETUP_STATE_NEEDS_WIFI:
        return "needs_wifi";
    case OWL_SETUP_STATE_NEEDS_SPOTIFY:
        return "needs_spotify";
    case OWL_SETUP_STATE_READY:
        return "ready";
    }
    return "needs_wifi";
}

uint32_t owl_prov_take_actions(owl_prov_t *p)
{
    uint32_t actions = p->actions;
    p->actions = 0;
    return actions;
}

static void end_session(owl_prov_t *p)
{
    memset(&p->session, 0, sizeof p->session);
    p->session_expires_ms = 0;
    p->code[0] = '\0';
}

const char *owl_prov_accept_code(owl_prov_t *p, const char *code, const char *state, int64_t now_ms)
{
    if (p->session_expires_ms == 0) {
        return "no_session";
    }
    if (now_ms >= p->session_expires_ms) {
        end_session(p);
        return "expired";
    }
    if (p->code[0] != '\0') {
        return "busy";
    }
    if (!spotify_state_matches(&p->session, state)) {
        return "bad_state";
    }
    if (!spotify_code_valid(code)) {
        return "bad_code";
    }
    owl_utf8_copy(p->code, sizeof p->code, code);
    p->actions |= OWL_PROV_DO_EXCHANGE;
    return NULL;
}

void owl_prov_finish_exchange(owl_prov_t *p, bool ok, const char *refresh_token)
{
    if (ok && refresh_token != NULL && refresh_token[0] != '\0' &&
        strlen(refresh_token) < sizeof p->settings.refresh_token) {
        owl_utf8_copy(p->settings.refresh_token, sizeof p->settings.refresh_token, refresh_token);
        p->actions |= OWL_PROV_DO_SAVE;
    }
    end_session(p);
}

bool owl_prov_apply_refresh(owl_prov_t *p, spotify_token_result_t result, const char *refresh_token)
{
    if (result == SPOTIFY_TOKEN_LOG_IN_AGAIN || result == SPOTIFY_TOKEN_BAD_CLIENT) {
        p->settings.refresh_token[0] = '\0';
        p->actions |= OWL_PROV_DO_SAVE;
        return true;
    }
    if (result == SPOTIFY_TOKEN_OK && refresh_token != NULL && refresh_token[0] != '\0' &&
        strlen(refresh_token) < sizeof p->settings.refresh_token &&
        strcmp(refresh_token, p->settings.refresh_token) != 0) {
        owl_utf8_copy(p->settings.refresh_token, sizeof p->settings.refresh_token, refresh_token);
        p->actions |= OWL_PROV_DO_SAVE;
    }
    return false;
}

/* ---- output -------------------------------------------------------------------------------- */

bool owl_prov_emit(struct cJSON *obj, char *out, size_t cap)
{
    char *json = obj ? cJSON_PrintUnformatted(obj) : NULL;
    cJSON_Delete(obj);
    bool ok = false;
    if (json != NULL) {
        int n = snprintf(out, cap, OWL_PROV_PREFIX "%s\n", json);
        ok = n > 0 && (size_t)n < cap && (size_t)n <= OWL_PROV_LINE_MAX;
        cJSON_free(json);
    }
    if (!ok && cap > 0) {
        out[0] = '\0';
    }
    return ok;
}

static cJSON *reply(int id, bool ok)
{
    cJSON *obj = cJSON_CreateObject();
    cJSON_AddNumberToObject(obj, "id", id);
    cJSON_AddBoolToObject(obj, "ok", ok);
    return obj;
}

static void respond(cJSON *obj, int id, char *out, size_t cap)
{
    if (!owl_prov_emit(obj, out, cap)) {
        snprintf(out, cap, OWL_PROV_PREFIX "{\"id\":%d,\"ok\":false,\"error\":\"too_long\"}\n", id);
    }
}

static void respond_error(int id, const char *code, char *out, size_t cap)
{
    cJSON *obj = reply(id, false);
    cJSON_AddStringToObject(obj, "error", code);
    respond(obj, id, out, cap);
}

bool owl_prov_event(char *out, size_t cap, const char *event, const char *state, const char *key,
                    const char *value)
{
    cJSON *obj = cJSON_CreateObject();
    cJSON_AddStringToObject(obj, "event", event);
    cJSON_AddStringToObject(obj, "state", state);
    if (key != NULL && value != NULL) {
        cJSON_AddStringToObject(obj, key, value);
    }
    return owl_prov_emit(obj, out, cap);
}

/* ---- commands ------------------------------------------------------------------------------ */

static const char *str_param(const cJSON *req, const char *name)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(req, name);
    return cJSON_IsString(v) ? v->valuestring : NULL;
}

static int find_network(const owl_prov_t *p, const char *ssid)
{
    for (int i = 0; i < p->settings.n_networks; i++) {
        if (strcmp(p->settings.networks[i].ssid, ssid) == 0) {
            return i;
        }
    }
    return -1;
}

static void cmd_hello(owl_prov_t *p, int id, char *out, size_t cap)
{
    cJSON *obj = reply(id, true);
    cJSON_AddStringToObject(obj, "name", p->name);
    cJSON_AddStringToObject(obj, "fw", p->fw);
    cJSON_AddNumberToObject(obj, "protocol", OWL_PROV_PROTOCOL);
    cJSON_AddStringToObject(obj, "setup", owl_prov_setup_state_name(owl_prov_setup_state(p)));
    cJSON_AddBoolToObject(obj, "linked", p->settings.refresh_token[0] != '\0');
    cJSON_AddStringToObject(obj, "client_id", p->settings.client_id);
    cJSON_AddStringToObject(obj, "redirect_uri", p->settings.redirect_uri);
    cJSON_AddStringToObject(obj, "ip", p->ip);
    cJSON *networks = cJSON_AddArrayToObject(obj, "networks");
    for (int i = 0; i < p->settings.n_networks; i++) {
        cJSON_AddItemToArray(networks, cJSON_CreateString(p->settings.networks[i].ssid));
    }
    respond(obj, id, out, cap);
}

static const char *cmd_wifi_add(owl_prov_t *p, const cJSON *req)
{
    const char *ssid = str_param(req, "ssid");
    const char *password = str_param(req, "password");
    size_t ssid_len = ssid ? strlen(ssid) : 0;
    size_t pass_len = password ? strlen(password) : 0;
    if (ssid_len == 0 || ssid_len >= OWL_SSID_LEN) {
        return "bad_ssid";
    }
    if (password == NULL || (pass_len != 0 && (pass_len < 8 || pass_len >= OWL_WIFI_PASSWORD_LEN))) {
        return "bad_password";
    }
    int index = find_network(p, ssid);
    if (index < 0) {
        if (p->settings.n_networks == OWL_PROV_MAX_NETWORKS) {
            return "full";
        }
        index = p->settings.n_networks++;
        owl_utf8_copy(p->settings.networks[index].ssid, OWL_SSID_LEN, ssid);
    }
    owl_utf8_copy(p->settings.networks[index].password, OWL_WIFI_PASSWORD_LEN, password);
    p->actions |= OWL_PROV_DO_SAVE | OWL_PROV_DO_JOIN_WIFI;
    return NULL;
}

static const char *cmd_wifi_remove(owl_prov_t *p, const cJSON *req)
{
    const char *ssid = str_param(req, "ssid");
    int index = ssid ? find_network(p, ssid) : -1;
    if (index < 0) {
        return "not_found";
    }
    memmove(&p->settings.networks[index], &p->settings.networks[index + 1],
            sizeof(owl_wifi_network_t) * (size_t)(p->settings.n_networks - index - 1));
    p->settings.n_networks--;
    memset(&p->settings.networks[p->settings.n_networks], 0, sizeof(owl_wifi_network_t));
    p->actions |= OWL_PROV_DO_SAVE | OWL_PROV_DO_JOIN_WIFI;
    return NULL;
}

static const char *cmd_spotify_client(owl_prov_t *p, const cJSON *req)
{
    const char *client_id = str_param(req, "client_id");
    const char *redirect_uri = str_param(req, "redirect_uri");
    if (!spotify_client_id_valid(client_id)) {
        return "bad_client_id";
    }
    if (!spotify_redirect_uri_valid(redirect_uri)) {
        return "bad_redirect_uri";
    }
    if (strcmp(client_id, p->settings.client_id) != 0 ||
        strcmp(redirect_uri, p->settings.redirect_uri) != 0) {
        /* Tokens belong to one client and redirect URI; a new pair needs a new login. */
        p->settings.refresh_token[0] = '\0';
        end_session(p);
    }
    owl_utf8_copy(p->settings.client_id, sizeof p->settings.client_id, client_id);
    owl_utf8_copy(p->settings.redirect_uri, sizeof p->settings.redirect_uri, redirect_uri);
    p->actions |= OWL_PROV_DO_SAVE;
    return NULL;
}

static void cmd_spotify_begin(owl_prov_t *p, int id, int64_t now_ms, char *out, size_t cap)
{
    char url[768];
    if (p->settings.client_id[0] == '\0' || p->settings.redirect_uri[0] == '\0') {
        respond_error(id, "no_client_id", out, cap);
        return;
    }
    end_session(p);
    spotify_pkce_new(&p->session, p->random, p->network_up ? p->ip : NULL);
    if (!spotify_authorize_url(p->settings.client_id, p->settings.redirect_uri, &p->session, url,
                               sizeof url)) {
        end_session(p);
        respond_error(id, "too_long", out, cap);
        return;
    }
    p->session_expires_ms = now_ms + OWL_PROV_SESSION_MS;
    cJSON *obj = reply(id, true);
    cJSON_AddStringToObject(obj, "authorize_url", url);
    respond(obj, id, out, cap);
}

bool owl_prov_handle_line(owl_prov_t *p, const char *line, int64_t now_ms, char *out, size_t cap)
{
    size_t prefix_len = strlen(OWL_PROV_PREFIX);
    if (line == NULL || strncmp(line, OWL_PROV_PREFIX, prefix_len) != 0) {
        return false;
    }
    const char *json = line + prefix_len;
    size_t len = strcspn(json, "\r\n");
    cJSON *req = cJSON_ParseWithLength(json, len);
    if (!cJSON_IsObject(req)) {
        cJSON_Delete(req);
        respond_error(0, "bad_request", out, cap);
        return true;
    }
    const cJSON *id_item = cJSON_GetObjectItemCaseSensitive(req, "id");
    int id = cJSON_IsNumber(id_item) ? id_item->valueint : 0;
    const char *cmd = str_param(req, "cmd");
    const char *error = NULL;
    bool replied = false;

    if (cmd == NULL) {
        error = "bad_request";
    } else if (strcmp(cmd, "hello") == 0) {
        cmd_hello(p, id, out, cap);
        replied = true;
    } else if (strcmp(cmd, "wifi_add") == 0) {
        error = cmd_wifi_add(p, req);
    } else if (strcmp(cmd, "wifi_remove") == 0) {
        error = cmd_wifi_remove(p, req);
    } else if (strcmp(cmd, "spotify_client") == 0) {
        error = cmd_spotify_client(p, req);
    } else if (strcmp(cmd, "spotify_begin") == 0) {
        cmd_spotify_begin(p, id, now_ms, out, cap);
        replied = true;
    } else if (strcmp(cmd, "spotify_code") == 0) {
        error = owl_prov_accept_code(p, str_param(req, "code"), str_param(req, "state"), now_ms);
        if (error == NULL) {
            cJSON *obj = reply(id, true);
            cJSON_AddBoolToObject(obj, "accepted", true);
            respond(obj, id, out, cap);
            replied = true;
        }
    } else if (strcmp(cmd, "spotify_logout") == 0) {
        p->settings.refresh_token[0] = '\0';
        end_session(p);
        p->actions |= OWL_PROV_DO_SAVE;
    } else {
        error = "unknown_cmd";
    }

    if (!replied) {
        if (error != NULL) {
            respond_error(id, error, out, cap);
        } else {
            respond(reply(id, true), id, out, cap);
        }
    }
    cJSON_Delete(req);
    return true;
}
