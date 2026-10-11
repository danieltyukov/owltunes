#include "owl_shell.h"

#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "owl_prov.h"
#include "owl_text.h"

/* ---- parsing ------------------------------------------------------------------------------- */

typedef enum { ARG_NONE, ARG_AUTH, ARG_VOLUME, ARG_DEVICE } arg_kind_t;

typedef struct {
    const char *word;
    owl_shell_verb_t verb;
    arg_kind_t arg;
} verb_entry_t;

static const verb_entry_t VERBS[] = {
    {"help", OWL_SHELL_HELP, ARG_NONE},       {"info", OWL_SHELL_INFO, ARG_NONE},
    {"status", OWL_SHELL_STATUS, ARG_NONE},   {"auth", OWL_SHELL_AUTH, ARG_AUTH},
    {"devices", OWL_SHELL_DEVICES, ARG_NONE}, {"play", OWL_SHELL_PLAY, ARG_NONE},
    {"pause", OWL_SHELL_PAUSE, ARG_NONE},     {"toggle", OWL_SHELL_TOGGLE, ARG_NONE},
    {"next", OWL_SHELL_NEXT, ARG_NONE},       {"prev", OWL_SHELL_PREV, ARG_NONE},
    {"previous", OWL_SHELL_PREV, ARG_NONE},   {"vol", OWL_SHELL_VOLUME, ARG_VOLUME},
    {"volume", OWL_SHELL_VOLUME, ARG_VOLUME}, {"like", OWL_SHELL_LIKE, ARG_NONE},
    {"unlike", OWL_SHELL_UNLIKE, ARG_NONE},   {"transfer", OWL_SHELL_TRANSFER, ARG_DEVICE},
};

static bool is_space(char c)
{
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

static const char *skip_space(const char *s)
{
    while (is_space(*s)) {
        s++;
    }
    return s;
}

static const char *skip_word(const char *s)
{
    while (*s != '\0' && !is_space(*s)) {
        s++;
    }
    return s;
}

/* A device id: letters, digits, "_" and "-". */
static bool is_id_char(char c)
{
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-';
}

/* "40", "+5" or "-10": at most three digits, at most 100. */
static bool parse_volume(const char *arg, size_t len, owl_shell_cmd_t *out)
{
    size_t i = 0;
    int sign = 0;
    if (len > 0 && (arg[0] == '+' || arg[0] == '-')) {
        sign = arg[0] == '+' ? 1 : -1;
        i = 1;
    }
    if (len - i < 1 || len - i > 3) {
        return false;
    }
    int32_t value = 0;
    for (; i < len; i++) {
        if (arg[i] < '0' || arg[i] > '9') {
            return false;
        }
        value = value * 10 + (arg[i] - '0');
    }
    if (value > 100) {
        return false;
    }
    out->relative = sign != 0;
    out->value = sign < 0 ? -value : value;
    return true;
}

static bool parse_arg(arg_kind_t kind, const char *arg, size_t len, owl_shell_cmd_t *out)
{
    switch (kind) {
    case ARG_NONE:
        return len == 0;
    case ARG_AUTH:
        if (len == 7 && strncmp(arg, "refresh", 7) == 0) {
            out->value = 1;
        }
        return len == 0 || out->value == 1;
    case ARG_VOLUME:
        return parse_volume(arg, len, out);
    case ARG_DEVICE:
        if (len == 0 || len > OWL_SHELL_ARG_LEN) {
            return false;
        }
        for (size_t i = 0; i < len; i++) {
            if (!is_id_char(arg[i])) {
                return false;
            }
        }
        memcpy(out->arg, arg, len);
        out->arg[len] = '\0';
        return true;
    }
    return false;
}

void owl_shell_parse(const char *line, owl_shell_cmd_t *out)
{
    memset(out, 0, sizeof *out);
    out->verb = OWL_SHELL_NONE;
    if (line == NULL) {
        return;
    }
    const char *word = skip_space(line);
    if (*word == '\0') {
        return;
    }
    const char *word_end = skip_word(word);
    const char *arg = skip_space(word_end);
    const char *arg_end = skip_word(arg);
    bool extra = *skip_space(arg_end) != '\0';
    size_t word_len = (size_t)(word_end - word);
    out->verb = OWL_SHELL_UNKNOWN;
    for (size_t i = 0; i < sizeof VERBS / sizeof VERBS[0]; i++) {
        if (strlen(VERBS[i].word) == word_len && strncmp(VERBS[i].word, word, word_len) == 0) {
            out->verb = VERBS[i].verb;
            out->bad_arg = extra || !parse_arg(VERBS[i].arg, arg, (size_t)(arg_end - arg), out);
            return;
        }
    }
}

const char *owl_shell_verb_name(owl_shell_verb_t v)
{
    switch (v) {
    case OWL_SHELL_HELP:
        return "help";
    case OWL_SHELL_INFO:
        return "info";
    case OWL_SHELL_STATUS:
        return "status";
    case OWL_SHELL_AUTH:
        return "auth";
    case OWL_SHELL_DEVICES:
        return "devices";
    case OWL_SHELL_PLAY:
        return "play";
    case OWL_SHELL_PAUSE:
        return "pause";
    case OWL_SHELL_TOGGLE:
        return "toggle";
    case OWL_SHELL_NEXT:
        return "next";
    case OWL_SHELL_PREV:
        return "prev";
    case OWL_SHELL_VOLUME:
        return "volume";
    case OWL_SHELL_LIKE:
        return "like";
    case OWL_SHELL_UNLIKE:
        return "unlike";
    case OWL_SHELL_TRANSFER:
        return "transfer";
    case OWL_SHELL_NONE:
    case OWL_SHELL_UNKNOWN:
        break;
    }
    return "";
}

bool owl_shell_is_playback(owl_shell_verb_t v)
{
    return v >= OWL_SHELL_PLAY && v <= OWL_SHELL_TRANSFER;
}

/* ---- resolving ----------------------------------------------------------------------------- */

static int32_t clamp_percent(int32_t v)
{
    return v < 0 ? 0 : (v > 100 ? 100 : v);
}

static const char *device_problem(const owl_player_t *p)
{
    if (p->status == OWL_PLAYER_NO_DEVICE) {
        return "no_active_device";
    }
    if (p->has_device && p->device.is_restricted) {
        return "device_restricted";
    }
    return NULL;
}

static bool all_digits(const char *s)
{
    if (*s == '\0') {
        return false;
    }
    for (; *s; s++) {
        if (*s < '0' || *s > '9') {
            return false;
        }
    }
    return true;
}

/* A device list holds at most OWL_LIST_MAX_ITEMS (50) entries, so one or two digits name a line
 * of the last "devices" answer; anything else is a device id (Spotify uses 40 hex characters). */
static const char *resolve_transfer(const char *arg, const owl_list_page_t *devices, owl_cmd_t *cmd)
{
    size_t len = strlen(arg);
    if (len > 2 || !all_digits(arg)) {
        if (len >= sizeof cmd->uri) {
            return "no_such_device"; /* the model keeps ids of up to 63 characters */
        }
        owl_cmd_set(cmd, OWL_CMD_TRANSFER, 0, arg);
        return NULL;
    }
    int n = len == 1 ? arg[0] - '0' : (arg[0] - '0') * 10 + (arg[1] - '0');
    if (devices == NULL || devices->kind != OWL_LIST_DEVICES || n < 1 || n > devices->count) {
        return "no_such_device";
    }
    const owl_list_item_t *item = &devices->items[n - 1];
    if (item->disabled) {
        return "device_restricted";
    }
    owl_cmd_set(cmd, OWL_CMD_TRANSFER, 0, item->uri);
    return NULL;
}

const char *owl_shell_resolve(const owl_shell_cmd_t *c, const owl_player_t *p, const owl_list_page_t *devices,
                              owl_cmd_t *cmd)
{
    memset(cmd, 0, sizeof *cmd);
    if (!owl_shell_is_playback(c->verb)) {
        return "not_playback";
    }
    const char *problem = device_problem(p);
    switch (c->verb) {
    case OWL_SHELL_PLAY:
    case OWL_SHELL_PAUSE:
    case OWL_SHELL_TOGGLE:
    case OWL_SHELL_NEXT:
    case OWL_SHELL_PREV: {
        if (problem != NULL) {
            return problem;
        }
        owl_cmd_type_t type = OWL_CMD_PLAY;
        if (c->verb == OWL_SHELL_PAUSE || (c->verb == OWL_SHELL_TOGGLE && p->status == OWL_PLAYER_PLAYING)) {
            type = OWL_CMD_PAUSE;
        } else if (c->verb == OWL_SHELL_NEXT) {
            type = OWL_CMD_NEXT;
        } else if (c->verb == OWL_SHELL_PREV) {
            type = OWL_CMD_PREV;
        }
        owl_cmd_set(cmd, type, 0, NULL);
        return NULL;
    }
    case OWL_SHELL_VOLUME: {
        if (problem != NULL) {
            return problem;
        }
        if (p->has_device && !p->device.supports_volume) {
            return "volume_unsupported";
        }
        int32_t target = c->value;
        if (c->relative) {
            if (!p->has_device || p->device.volume_percent < 0) {
                return "volume_unknown";
            }
            target = p->device.volume_percent + c->value;
        }
        owl_cmd_set(cmd, OWL_CMD_VOLUME, clamp_percent(target), NULL);
        return NULL;
    }
    case OWL_SHELL_LIKE:
    case OWL_SHELL_UNLIKE:
        /* Like the app: only Spotify tracks, never local files or episodes. */
        if (!p->has_track || p->track.kind != OWL_ITEM_TRACK ||
            strncmp(p->track.uri, "spotify:track:", 14) != 0) {
            return "no_track";
        }
        owl_cmd_set(cmd, c->verb == OWL_SHELL_LIKE ? OWL_CMD_LIKE : OWL_CMD_UNLIKE, 0, p->track.uri);
        return NULL;
    case OWL_SHELL_TRANSFER:
        return resolve_transfer(c->arg, devices, cmd);
    default:
        break;
    }
    return "not_playback";
}

const char *owl_shell_cmd_name(owl_cmd_type_t type)
{
    switch (type) {
    case OWL_CMD_PLAY:
        return "play";
    case OWL_CMD_PAUSE:
        return "pause";
    case OWL_CMD_NEXT:
        return "next";
    case OWL_CMD_PREV:
        return "prev";
    case OWL_CMD_SEEK:
        return "seek";
    case OWL_CMD_VOLUME:
        return "volume";
    case OWL_CMD_SHUFFLE:
        return "shuffle";
    case OWL_CMD_REPEAT:
        return "repeat";
    case OWL_CMD_LIKE:
        return "like";
    case OWL_CMD_UNLIKE:
        return "unlike";
    case OWL_CMD_PLAY_CONTEXT:
        return "play_context";
    case OWL_CMD_PLAY_URIS:
        return "play_uris";
    case OWL_CMD_TRANSFER:
        return "transfer";
    case OWL_CMD_QUEUE_ADD:
        return "queue_add";
    case OWL_CMD_NONE:
        break;
    }
    return "";
}

/* ---- output -------------------------------------------------------------------------------- */

static cJSON *event(const char *name, const char *state)
{
    cJSON *obj = cJSON_CreateObject();
    cJSON_AddStringToObject(obj, "event", name);
    if (state != NULL) {
        cJSON_AddStringToObject(obj, "state", state);
    }
    return obj;
}

/* Add text shortened to cap - 1 bytes on a code point boundary; leave it out when cap is 0. */
static void add_text(cJSON *obj, const char *key, const char *text, size_t cap)
{
    char buf[OWL_NAME_LEN];
    if (cap == 0) {
        return;
    }
    owl_utf8_copy(buf, cap < sizeof buf ? cap : sizeof buf, text);
    cJSON_AddStringToObject(obj, key, buf);
}

static const char *str_or_empty(const char *s)
{
    return s != NULL ? s : "";
}

bool owl_shell_cmd_line(char *out, size_t cap, const char *state, const char *cmd, const char *error,
                        int32_t retry_s)
{
    cJSON *obj = event("cmd", state);
    if (cmd != NULL && cmd[0] != '\0') {
        cJSON_AddStringToObject(obj, "cmd", cmd);
    }
    if (error != NULL) {
        cJSON_AddStringToObject(obj, "error", error);
    }
    if (retry_s > 0) {
        cJSON_AddNumberToObject(obj, "retry_s", retry_s);
    }
    return owl_prov_emit(obj, out, cap);
}

bool owl_shell_event_line(char *out, size_t cap, const char *name, const char *state, const char *key,
                          const char *value, const char *num_key, int64_t num)
{
    cJSON *obj = event(name, state);
    if (key != NULL) {
        cJSON_AddStringToObject(obj, key, str_or_empty(value));
    }
    if (num_key != NULL) {
        cJSON_AddNumberToObject(obj, num_key, (double)num);
    }
    return owl_prov_emit(obj, out, cap);
}

static const char *status_name(owl_player_status_t s)
{
    switch (s) {
    case OWL_PLAYER_NO_DEVICE:
        return "no_device";
    case OWL_PLAYER_PAUSED:
        return "paused";
    case OWL_PLAYER_PLAYING:
        return "playing";
    case OWL_PLAYER_UNKNOWN:
        break;
    }
    return "unknown";
}

static const char *kind_name(owl_item_kind_t k)
{
    switch (k) {
    case OWL_ITEM_TRACK:
        return "track";
    case OWL_ITEM_EPISODE:
        return "episode";
    case OWL_ITEM_AD:
        return "ad";
    case OWL_ITEM_UNKNOWN:
        break;
    }
    return "unknown";
}

static const char *link_name(owl_link_t link)
{
    switch (link) {
    case OWL_LINK_API:
        return "api";
    case OWL_LINK_BLE:
        return "ble";
    case OWL_LINK_NONE:
        break;
    }
    return "none";
}

static const char *repeat_name(owl_repeat_t r)
{
    return r == OWL_REPEAT_TRACK ? "track" : (r == OWL_REPEAT_CONTEXT ? "context" : "off");
}

static cJSON *player_json(const owl_player_t *p, int64_t now_ms, owl_link_t link, int32_t wait_s,
                          size_t text_cap)
{
    cJSON *obj = event("player", NULL);
    cJSON_AddStringToObject(obj, "status", status_name(p->status));
    if (p->has_track || p->track.kind == OWL_ITEM_AD) {
        cJSON_AddStringToObject(obj, "kind", kind_name(p->track.kind));
    }
    if (p->has_track) {
        add_text(obj, "title", p->track.title, text_cap);
        add_text(obj, "artist", p->track.subtitle, text_cap);
        add_text(obj, "album", p->track.album, text_cap);
        cJSON_AddStringToObject(obj, "uri", p->track.uri);
        cJSON_AddNumberToObject(obj, "progress_ms", owl_player_progress_now(p, now_ms));
        cJSON_AddNumberToObject(obj, "duration_ms", p->track.duration_ms);
        if (p->liked_known) {
            cJSON_AddBoolToObject(obj, "liked", p->liked);
        } else {
            cJSON_AddNullToObject(obj, "liked");
        }
    }
    if (p->has_device) {
        add_text(obj, "device", p->device.name, text_cap);
        cJSON_AddStringToObject(obj, "device_id", p->device.id);
        cJSON_AddStringToObject(obj, "device_type", p->device.type);
        if (p->device.volume_percent >= 0) {
            cJSON_AddNumberToObject(obj, "volume", p->device.volume_percent);
        } else {
            cJSON_AddNullToObject(obj, "volume");
        }
        cJSON_AddBoolToObject(obj, "supports_volume", p->device.supports_volume);
        cJSON_AddBoolToObject(obj, "restricted", p->device.is_restricted);
    }
    cJSON_AddBoolToObject(obj, "shuffle", p->shuffle);
    cJSON_AddStringToObject(obj, "repeat", repeat_name(p->repeat));
    if (p->context_uri[0] != '\0') {
        cJSON_AddStringToObject(obj, "context", p->context_uri);
    }
    cJSON_AddStringToObject(obj, "link", link_name(link));
    cJSON_AddNumberToObject(obj, "wait_s", wait_s);
    return obj;
}

bool owl_shell_player_line(char *out, size_t cap, const owl_player_t *p, int64_t now_ms, owl_link_t link,
                           int32_t wait_s)
{
    /* Titles full of quotes or control characters grow when escaped: shorten, then drop them. */
    static const size_t text_caps[] = {96, 32, 0};
    for (size_t i = 0; i < sizeof text_caps / sizeof text_caps[0]; i++) {
        if (owl_prov_emit(player_json(p, now_ms, link, wait_s, text_caps[i]), out, cap)) {
            return true;
        }
    }
    return false;
}

bool owl_shell_device_line(char *out, size_t cap, int n, const owl_list_item_t *item)
{
    static const size_t text_caps[] = {96, 32, 0};
    for (size_t i = 0; i < sizeof text_caps / sizeof text_caps[0]; i++) {
        cJSON *obj = event("device", NULL);
        cJSON_AddNumberToObject(obj, "n", n);
        cJSON_AddStringToObject(obj, "id", item->uri);
        add_text(obj, "name", item->title, text_caps[i]);
        add_text(obj, "type", item->subtitle, text_caps[i] > 0 ? OWL_TYPE_LEN : 0);
        cJSON_AddBoolToObject(obj, "active", item->active);
        cJSON_AddBoolToObject(obj, "restricted", item->disabled);
        if (owl_prov_emit(obj, out, cap)) {
            return true;
        }
    }
    return false;
}

bool owl_shell_player_changed(const owl_player_t *a, const owl_player_t *b)
{
    return a->status != b->status || a->has_track != b->has_track || a->track.kind != b->track.kind ||
           strcmp(a->track.uri, b->track.uri) != 0 || strcmp(a->track.title, b->track.title) != 0 ||
           a->has_device != b->has_device || strcmp(a->device.id, b->device.id) != 0 ||
           a->device.volume_percent != b->device.volume_percent ||
           a->device.supports_volume != b->device.supports_volume ||
           a->device.is_restricted != b->device.is_restricted || a->shuffle != b->shuffle ||
           a->repeat != b->repeat || a->liked != b->liked || a->liked_known != b->liked_known ||
           strcmp(a->context_uri, b->context_uri) != 0;
}

bool owl_shell_info_line(char *out, size_t cap, const owl_shell_info_t *info)
{
    char led[8];
    snprintf(led, sizeof led, "#%02x%02x%02x", info->led.r, info->led.g, info->led.b);
    cJSON *obj = event("info", NULL);
    cJSON_AddStringToObject(obj, "board", str_or_empty(info->board));
    cJSON_AddStringToObject(obj, "name", str_or_empty(info->name));
    cJSON_AddStringToObject(obj, "fw", str_or_empty(info->fw));
    cJSON_AddNumberToObject(obj, "uptime_s", (double)info->uptime_s);
    cJSON_AddStringToObject(obj, "reset", str_or_empty(info->reset));
    cJSON_AddStringToObject(obj, "partition", str_or_empty(info->partition));
    cJSON_AddNumberToObject(obj, "flash_kb", info->flash_kb);
    cJSON_AddNumberToObject(obj, "psram_kb", info->psram_kb);
    cJSON_AddNumberToObject(obj, "psram_free_kb", info->psram_free_kb);
    cJSON_AddNumberToObject(obj, "heap_free_kb", info->heap_free_kb);
    cJSON_AddNumberToObject(obj, "heap_min_kb", info->heap_min_kb);
    cJSON_AddStringToObject(obj, "status", str_or_empty(info->status));
    cJSON_AddStringToObject(obj, "led", led);
    cJSON_AddStringToObject(obj, "wifi", str_or_empty(info->wifi));
    cJSON_AddStringToObject(obj, "ssid", str_or_empty(info->ssid));
    cJSON_AddNumberToObject(obj, "rssi", info->rssi);
    cJSON_AddStringToObject(obj, "ip", str_or_empty(info->ip));
    cJSON_AddBoolToObject(obj, "linked", info->linked);
    cJSON_AddStringToObject(obj, "utc", str_or_empty(info->utc));
    return owl_prov_emit(obj, out, cap);
}

bool owl_shell_help_line(char *out, size_t cap)
{
    cJSON *obj = event("help", NULL);
    cJSON_AddStringToObject(obj, "commands",
                            "help, info, status, auth [refresh], devices, play, pause, toggle, next, prev, "
                            "vol <0-100|+n|-n>, like, unlike, transfer <n|device id>");
    return owl_prov_emit(obj, out, cap);
}
