#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "owl_cmd.h"
#include "owl_model.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OWL_PRESET_COUNT 8
#define OWL_NAV_DEPTH 6
#define OWL_EFFECTS_MAX_CMDS 2
#define OWL_VOLUME_STEP 2
#define OWL_SEEK_STEP_MS 5000
#define OWL_VOLUME_OVERLAY_MS 1200

typedef enum { OWL_SCREEN_NOW_PLAYING, OWL_SCREEN_LIBRARY, OWL_SCREEN_BROWSE, OWL_SCREEN_PRESETS } owl_screen_t;

/* How the owl reaches Spotify right now. */
typedef enum {
    OWL_LINK_NONE, /* no internet and no Bluetooth host */
    OWL_LINK_BLE,  /* Bluetooth media keys only */
    OWL_LINK_API,  /* Spotify Web API reachable */
} owl_link_t;

typedef enum {
    OWL_LIB_PLAYLISTS,
    OWL_LIB_LIKED,
    OWL_LIB_ALBUMS,
    OWL_LIB_RECENT,
    OWL_LIB_DEVICES,
    OWL_LIB_PRESETS,
    OWL_LIB_COUNT,
} owl_lib_entry_t;

typedef enum {
    OWL_IN_RING,
    OWL_IN_TAP,
    OWL_IN_LONG_PRESS,
    OWL_IN_SWIPE_LEFT,
    OWL_IN_SWIPE_RIGHT,
    OWL_IN_SWIPE_UP,
    OWL_IN_EAR_LEFT,
    OWL_IN_EAR_RIGHT,
    OWL_IN_EAR_LEFT_HOLD,
    OWL_IN_EAR_LEFT_RELEASE,
    OWL_IN_EAR_RIGHT_HOLD,
    OWL_IN_BEAK,
    OWL_IN_BEAK_HOLD,
    OWL_IN_BEAK_DOUBLE,
} owl_input_kind_t;

typedef struct {
    owl_input_kind_t kind;
    int32_t steps; /* OWL_IN_RING: detent steps, positive clockwise */
} owl_input_t;

typedef enum {
    OWL_HAPTIC_NONE,
    OWL_HAPTIC_TICK,
    OWL_HAPTIC_BUMP,
    OWL_HAPTIC_CONFIRM,
    OWL_HAPTIC_HEARTBEAT,
    OWL_HAPTIC_BUZZ,
    OWL_HAPTIC_PRESET,
} owl_haptic_t;

typedef enum { OWL_KEY_NONE, OWL_KEY_PLAY_PAUSE, OWL_KEY_NEXT, OWL_KEY_PREV, OWL_KEY_VOL_UP, OWL_KEY_VOL_DOWN } owl_media_key_t;

typedef struct {
    owl_list_kind_t kind; /* OWL_LIST_NONE when nothing needs fetching */
    char uri[OWL_URI_LEN];
    uint32_t offset;
} owl_fetch_t;

/* Everything one input asks the rest of the firmware to do. */
typedef struct {
    uint8_t n_cmds;
    owl_cmd_t cmds[OWL_EFFECTS_MAX_CMDS];
    owl_fetch_t fetch;
    owl_haptic_t haptic;
    owl_media_key_t key; /* Bluetooth or USB media key to send */
    uint8_t key_repeat;
} owl_effects_t;

typedef struct {
    bool assigned;
    char uri[OWL_URI_LEN];
    char label[OWL_NAME_LEN];
} owl_preset_t;

typedef struct {
    owl_screen_t screen;
    owl_list_kind_t list_kind; /* OWL_SCREEN_BROWSE: what the list shows */
    char uri[OWL_URI_LEN];     /* OWL_SCREEN_BROWSE: the playlist or album being listed */
    int16_t cursor;
} owl_nav_frame_t;

typedef struct {
    owl_nav_frame_t nav[OWL_NAV_DEPTH]; /* nav[0] is always Now Playing */
    uint8_t depth;
    const owl_list_page_t *list; /* contents of the current BROWSE frame, NULL while loading */
    owl_preset_t presets[OWL_PRESET_COUNT];
    uint8_t preset_cursor;
    bool wheel_open; /* preset wheel opened by holding the left ear */
    int64_t volume_overlay_until_ms;
    owl_link_t link;
    bool hid_paired;
    bool ring_locked; /* in a pocket: ignore the ring */
} owl_app_t;

void owl_app_init(owl_app_t *app);

const owl_nav_frame_t *owl_app_frame(const owl_app_t *app);

/* Handle one input. Fills fx (always reset first) and applies optimistic results of the emitted
 * commands to player. */
void owl_app_handle(owl_app_t *app, owl_player_t *player, const owl_input_t *in, int64_t now_ms,
                    owl_effects_t *fx);

/* Deliver a fetched list. Ignored (returns false) unless it belongs to the current BROWSE frame.
 * The page must stay valid until it is replaced. */
bool owl_app_set_list(owl_app_t *app, const owl_list_page_t *page);

void owl_app_set_link(owl_app_t *app, owl_link_t link, bool hid_paired);

const char *owl_lib_entry_label(owl_lib_entry_t e);

#ifdef __cplusplus
}
#endif
