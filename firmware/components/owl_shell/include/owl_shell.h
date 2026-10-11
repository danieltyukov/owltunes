#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "owl_status.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The USB console's developer commands: lines typed without the @owl prefix, such as "info". The
 * owl answers with JSON lines in the @owl framing (docs/console.md), so a host script can follow
 * along. Pure: parsing and formatting only, no I/O. */

typedef enum {
    OWL_SHELL_NONE,    /* an empty line: ignore it */
    OWL_SHELL_UNKNOWN, /* not a command */
    OWL_SHELL_HELP,
    OWL_SHELL_INFO,
} owl_shell_verb_t;

typedef struct {
    owl_shell_verb_t verb;
    bool bad_arg; /* a known command with a missing, extra or malformed argument */
} owl_shell_cmd_t;

void owl_shell_parse(const char *line, owl_shell_cmd_t *out);

/* "help", "info"; "" for NONE and UNKNOWN. */
const char *owl_shell_verb_name(owl_shell_verb_t v);

/* The lines below are written as "@owl {...}\n" into out and are never longer than
 * OWL_SHELL_LINE_MAX bytes. Each returns false, with out set to "", when the line could not be
 * built. */
#define OWL_SHELL_LINE_MAX 1024

/* {"event":"cmd","state":"refused","cmd":"info"}; error and retry_s ("retry_s":N) are left out
 * when NULL or 0. */
bool owl_shell_cmd_line(char *out, size_t cap, const char *state, const char *cmd, const char *error,
                        int32_t retry_s);

/* {"event":"<event>","state":"<state>"} plus an optional string field (key NULL to leave it out)
 * and an optional number field (num_key NULL to leave it out). */
bool owl_shell_event_line(char *out, size_t cap, const char *event, const char *state, const char *key,
                          const char *value, const char *num_key, int64_t num);

typedef struct {
    const char *board; /* CONFIG_OWL_BOARD_NAME */
    const char *name;  /* "OwlTunes-7DF8" */
    const char *fw;    /* the app version */
    int64_t uptime_s;
    const char *reset;     /* why the chip last reset: "poweron", "usb", "panic", ... */
    const char *partition; /* the running app slot, "ota_0" or "ota_1" */
    uint32_t flash_kb;
    uint32_t psram_kb; /* 0 without PSRAM */
    uint32_t psram_free_kb;
    uint32_t heap_free_kb; /* internal RAM free now */
    uint32_t heap_min_kb;  /* internal RAM free at its lowest since boot */
    const char *status;    /* owl_status_name() */
    owl_rgb_t led;
    const char *wifi; /* the network state, as net_info reports it (docs/console.md) */
    const char *ssid; /* the joined network, "" when none */
    int rssi;         /* dBm, 0 when unknown */
    const char *ip;   /* "" when offline */
    bool linked;      /* a Spotify login is saved */
    const char *utc;  /* "2026-10-11T09:30:00Z" once the clock is set, else "" */
} owl_shell_info_t;

/* {"event":"info",...} with every field of info. NULL strings are written as "". */
bool owl_shell_info_line(char *out, size_t cap, const owl_shell_info_t *info);

/* {"event":"help","commands":"..."} listing every command. */
bool owl_shell_help_line(char *out, size_t cap);

#ifdef __cplusplus
}
#endif
