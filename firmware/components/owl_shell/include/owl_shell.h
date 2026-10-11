#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "owl_app.h"
#include "owl_cmd.h"
#include "owl_model.h"
#include "owl_status.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The USB console's developer commands: lines typed without the @owl prefix, such as "next" or
 * "vol +5". The owl answers with JSON lines in the @owl framing (docs/console.md), so a host
 * script can follow along. Pure: parsing and formatting only, no I/O. */

#define OWL_SHELL_ARG_LEN 63 /* the longest device id the console accepts (owl_cmd_t.uri holds 63) */

typedef enum {
    OWL_SHELL_NONE,    /* an empty line: ignore it */
    OWL_SHELL_UNKNOWN, /* not a command */
    OWL_SHELL_HELP,
    OWL_SHELL_INFO,
    OWL_SHELL_STATUS,
    OWL_SHELL_AUTH,
    OWL_SHELL_DEVICES,
    OWL_SHELL_PLAY,
    OWL_SHELL_PAUSE,
    OWL_SHELL_TOGGLE,
    OWL_SHELL_NEXT,
    OWL_SHELL_PREV,
    OWL_SHELL_VOLUME,
    OWL_SHELL_LIKE,
    OWL_SHELL_UNLIKE,
    OWL_SHELL_TRANSFER,
} owl_shell_verb_t;

typedef struct {
    owl_shell_verb_t verb;
    bool bad_arg;  /* a known command with a missing, extra or malformed argument */
    int32_t value; /* VOLUME: percent, or the change when relative; AUTH: 1 forces a refresh */
    bool relative; /* VOLUME: "vol +5" or "vol -5" */
    char arg[OWL_SHELL_ARG_LEN + 1]; /* TRANSFER: a device id, or the number of a "device" line */
} owl_shell_cmd_t;

void owl_shell_parse(const char *line, owl_shell_cmd_t *out);

/* "next", "volume", ...; "" for NONE and UNKNOWN. */
const char *owl_shell_verb_name(owl_shell_verb_t v);

/* True for the verbs that become a Spotify player or library command. */
bool owl_shell_is_playback(owl_shell_verb_t v);

/* What a playback verb asks Spotify to do now, given the last known player state and the last
 * device list (devices may be NULL). Returns NULL and fills cmd, or an error code:
 * "no_active_device", "device_restricted", "volume_unsupported", "volume_unknown", "no_track",
 * "no_such_device" or "not_playback". */
const char *owl_shell_resolve(const owl_shell_cmd_t *c, const owl_player_t *p, const owl_list_page_t *devices,
                              owl_cmd_t *cmd);

/* "play", "pause", "next", "prev", "volume", "like", "unlike", "transfer", ...; "" for others. */
const char *owl_shell_cmd_name(owl_cmd_type_t type);

/* The lines below are written as "@owl {...}\n" into out and are never longer than
 * OWL_SHELL_LINE_MAX bytes. Each returns false, with out set to "", when the line could not be
 * built. */
#define OWL_SHELL_LINE_MAX 1024

/* {"event":"cmd","state":"refused","cmd":"next"}; error and retry_s ("retry_s":N) are left out
 * when NULL or 0. */
bool owl_shell_cmd_line(char *out, size_t cap, const char *state, const char *cmd, const char *error,
                        int32_t retry_s);

/* {"event":"<event>","state":"<state>"} plus an optional string field (key NULL to leave it out)
 * and an optional number field (num_key NULL to leave it out). */
bool owl_shell_event_line(char *out, size_t cap, const char *event, const char *state, const char *key,
                          const char *value, const char *num_key, int64_t num);

/* {"event":"player","status":"playing","title":...}. link and wait_s describe the Web API
 * (OWL_LINK_BLE during a quota lockout; seconds until requests may go out again). Text fields are
 * shortened, and dropped as a last resort, so the line always fits. */
bool owl_shell_player_line(char *out, size_t cap, const owl_player_t *p, int64_t now_ms, owl_link_t link,
                           int32_t wait_s);

/* {"event":"device","n":1,"id":...,"name":...,"type":...,"active":true,"restricted":false} */
bool owl_shell_device_line(char *out, size_t cap, int n, const owl_list_item_t *item);

/* True when after differs from before in more than the playback position moving on. */
bool owl_shell_player_changed(const owl_player_t *before, const owl_player_t *after);

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
