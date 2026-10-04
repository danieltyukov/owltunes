#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OWL_ID_LEN 64
#define OWL_URI_LEN 64
#define OWL_NAME_LEN 128
#define OWL_URL_LEN 160
#define OWL_TYPE_LEN 24
#define OWL_LIST_MAX_ITEMS 50

typedef enum { OWL_ITEM_TRACK, OWL_ITEM_EPISODE, OWL_ITEM_AD, OWL_ITEM_UNKNOWN } owl_item_kind_t;

typedef struct {
    owl_item_kind_t kind;
    char uri[OWL_URI_LEN];
    char title[OWL_NAME_LEN];
    char subtitle[OWL_NAME_LEN]; /* artists for tracks, the show for episodes */
    char album[OWL_NAME_LEN];
    char art_url[OWL_URL_LEN];
    uint32_t duration_ms;
} owl_track_t;

typedef struct {
    char id[OWL_ID_LEN];
    char name[OWL_NAME_LEN];
    char type[OWL_TYPE_LEN];
    bool is_active;
    bool is_restricted;
    bool supports_volume;
    int8_t volume_percent; /* -1 when unknown */
} owl_device_t;

typedef enum { OWL_REPEAT_OFF, OWL_REPEAT_CONTEXT, OWL_REPEAT_TRACK } owl_repeat_t;

typedef enum { OWL_PLAYER_UNKNOWN, OWL_PLAYER_NO_DEVICE, OWL_PLAYER_PAUSED, OWL_PLAYER_PLAYING } owl_player_status_t;

typedef struct {
    owl_player_status_t status;
    bool has_track;
    owl_track_t track;
    bool has_device;
    owl_device_t device;
    char context_uri[OWL_URI_LEN];
    char context_name[OWL_NAME_LEN];
    uint32_t progress_ms;   /* playback position at progress_at_ms */
    int64_t progress_at_ms; /* local monotonic time when the position was sampled */
    bool shuffle;
    owl_repeat_t repeat;
    bool liked;
    bool liked_known;
} owl_player_t;

void owl_player_init(owl_player_t *p);

/* Position now: advances with the clock while playing, frozen otherwise, clamped to the track. */
uint32_t owl_player_progress_now(const owl_player_t *p, int64_t now_ms);

/* Time left in the track, 0 when there is no track or no known duration. */
uint32_t owl_player_remaining_ms(const owl_player_t *p, int64_t now_ms);

typedef enum {
    OWL_LIST_NONE,
    OWL_LIST_PLAYLISTS,
    OWL_LIST_SAVED_TRACKS,
    OWL_LIST_ALBUMS,
    OWL_LIST_RECENT,
    OWL_LIST_QUEUE,
    OWL_LIST_DEVICES,
    OWL_LIST_PLAYLIST_ITEMS,
    OWL_LIST_ALBUM_TRACKS,
} owl_list_kind_t;

typedef struct {
    char title[OWL_NAME_LEN];
    char subtitle[OWL_NAME_LEN];
    char uri[OWL_URI_LEN]; /* Spotify URI, or the device id in a device list */
    char art_url[OWL_URL_LEN];
    bool browsable; /* opening it lists its items (owned or collaborative playlists, albums) */
    bool active;    /* the device that is playing now */
    bool disabled;  /* cannot be selected (restricted device, local file) */
} owl_list_item_t;

typedef struct {
    owl_list_kind_t kind;
    char source_uri[OWL_URI_LEN]; /* the playlist or album an item list belongs to */
    uint16_t count;
    uint32_t offset;
    uint32_t total;
    bool has_more;
    owl_list_item_t items[OWL_LIST_MAX_ITEMS];
} owl_list_page_t;

void owl_list_page_init(owl_list_page_t *page, owl_list_kind_t kind, const char *source_uri);

#ifdef __cplusplus
}
#endif
