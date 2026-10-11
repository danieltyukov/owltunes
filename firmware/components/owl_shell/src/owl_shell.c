#include "owl_shell.h"

#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "owl_prov.h"

/* ---- parsing ------------------------------------------------------------------------------- */

typedef struct {
    const char *word;
    owl_shell_verb_t verb;
} verb_entry_t;

static const verb_entry_t VERBS[] = {
    {"help", OWL_SHELL_HELP},
    {"info", OWL_SHELL_INFO},
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
    bool extra = *skip_space(word_end) != '\0';
    size_t word_len = (size_t)(word_end - word);
    out->verb = OWL_SHELL_UNKNOWN;
    for (size_t i = 0; i < sizeof VERBS / sizeof VERBS[0]; i++) {
        if (strlen(VERBS[i].word) == word_len && strncmp(VERBS[i].word, word, word_len) == 0) {
            out->verb = VERBS[i].verb;
            out->bad_arg = extra; /* neither command takes an argument */
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
    case OWL_SHELL_NONE:
    case OWL_SHELL_UNKNOWN:
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
    cJSON_AddStringToObject(obj, "commands", "help, info");
    return owl_prov_emit(obj, out, cap);
}
