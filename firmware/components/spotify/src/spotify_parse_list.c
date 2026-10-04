#include <stdio.h>
#include <string.h>

#include "owl_text.h"
#include "spotify_json.h"
#include "spotify_parse.h"

static owl_list_item_t *next_item(owl_list_page_t *page, uint32_t *seen)
{
    (*seen)++;
    return page->count < OWL_LIST_MAX_ITEMS ? &page->items[page->count++] : NULL;
}

static void fill_from_track(const cJSON *track, owl_list_item_t *it)
{
    owl_track_t t;
    sj_parse_track(track, &t);
    owl_utf8_copy(it->title, sizeof it->title, t.title);
    owl_utf8_copy(it->subtitle, sizeof it->subtitle, t.subtitle);
    owl_utf8_copy(it->uri, sizeof it->uri, t.uri);
    owl_utf8_copy(it->art_url, sizeof it->art_url, t.art_url);
}

static void fill_playlist(const cJSON *pl, const char *my_user_id, owl_list_item_t *it)
{
    owl_utf8_copy(it->title, sizeof it->title, sj_str(pl, "name"));
    owl_utf8_copy(it->uri, sizeof it->uri, sj_str(pl, "uri"));
    owl_utf8_copy(it->art_url, sizeof it->art_url, sj_pick_image(sj_arr(pl, "images"), 300));
    const cJSON *owner = sj_obj(pl, "owner");
    const char *owner_id = owner ? sj_str(owner, "id") : NULL;
    bool mine = my_user_id != NULL && owner_id != NULL && strcmp(my_user_id, owner_id) == 0;
    it->browsable = mine || sj_bool(pl, "collaborative", false);
    if (it->browsable) {
        /* Spotify renamed playlist.tracks to playlist.items in February 2026. */
        const cJSON *counts = sj_obj(pl, "items");
        if (counts == NULL) {
            counts = sj_obj(pl, "tracks");
        }
        int64_t total = counts ? sj_int(counts, "total", -1) : -1;
        if (total >= 0) {
            snprintf(it->subtitle, sizeof it->subtitle, "%lld songs", (long long)total);
        }
    } else {
        const char *owner_name = owner ? sj_str(owner, "display_name") : NULL;
        owl_utf8_copy(it->subtitle, sizeof it->subtitle, "by ");
        owl_utf8_append(it->subtitle, sizeof it->subtitle, owner_name ? owner_name : owner_id);
    }
}

static void fill_album(const cJSON *album, owl_list_item_t *it)
{
    owl_utf8_copy(it->title, sizeof it->title, sj_str(album, "name"));
    sj_join_names(sj_arr(album, "artists"), it->subtitle, sizeof it->subtitle);
    owl_utf8_copy(it->uri, sizeof it->uri, sj_str(album, "uri"));
    owl_utf8_copy(it->art_url, sizeof it->art_url, sj_pick_image(sj_arr(album, "images"), 300));
    it->browsable = true;
}

static void fill_device(const cJSON *dev, owl_list_item_t *it)
{
    const char *id = sj_str(dev, "id");
    owl_utf8_copy(it->title, sizeof it->title, sj_str(dev, "name"));
    owl_utf8_copy(it->subtitle, sizeof it->subtitle, sj_str(dev, "type"));
    owl_utf8_copy(it->uri, sizeof it->uri, id);
    it->active = sj_bool(dev, "is_active", false);
    it->disabled = id == NULL || sj_bool(dev, "is_restricted", false);
}

static const char *array_key(owl_list_kind_t kind)
{
    switch (kind) {
    case OWL_LIST_QUEUE:
        return "queue";
    case OWL_LIST_DEVICES:
        return "devices";
    case OWL_LIST_NONE:
        return NULL;
    default:
        return "items";
    }
}

spotify_parse_result_t spotify_parse_list(owl_list_kind_t kind, const char *json, size_t len, const char *my_user_id,
                                          const char *source_uri, owl_list_page_t *out)
{
    const char *key = array_key(kind);
    if (key == NULL || json == NULL) {
        return SPOTIFY_PARSE_BAD_SHAPE;
    }
    cJSON *root = cJSON_ParseWithLength(json, len);
    if (root == NULL) {
        return SPOTIFY_PARSE_BAD_JSON;
    }
    const cJSON *arr = sj_arr(root, key);
    if (arr == NULL) {
        cJSON_Delete(root);
        return SPOTIFY_PARSE_BAD_SHAPE;
    }
    owl_list_page_init(out, kind, source_uri);
    uint32_t seen = 0;
    const cJSON *entry;
    cJSON_ArrayForEach(entry, arr)
    {
        const cJSON *track = NULL;
        switch (kind) {
        case OWL_LIST_PLAYLISTS: {
            owl_list_item_t *it = next_item(out, &seen);
            if (it != NULL) {
                fill_playlist(entry, my_user_id, it);
            }
            continue;
        }
        case OWL_LIST_ALBUMS: {
            const cJSON *album = sj_obj(entry, "album");
            owl_list_item_t *it = album ? next_item(out, &seen) : NULL;
            if (it != NULL) {
                fill_album(album, it);
            }
            continue;
        }
        case OWL_LIST_DEVICES: {
            owl_list_item_t *it = next_item(out, &seen);
            if (it != NULL) {
                fill_device(entry, it);
            }
            continue;
        }
        case OWL_LIST_SAVED_TRACKS:
        case OWL_LIST_RECENT:
            track = sj_obj(entry, "track");
            break;
        case OWL_LIST_PLAYLIST_ITEMS:
            /* Spotify renamed playlist item.track to item.item in February 2026. */
            track = sj_obj(entry, "item");
            if (track == NULL) {
                track = sj_obj(entry, "track");
            }
            break;
        default: /* QUEUE and ALBUM_TRACKS hold track objects directly */
            track = cJSON_IsObject(entry) ? entry : NULL;
            break;
        }
        if (track == NULL) {
            continue; /* removed or unavailable entry */
        }
        owl_list_item_t *it = next_item(out, &seen);
        if (it != NULL) {
            fill_from_track(track, it);
            it->disabled = sj_bool(entry, "is_local", false);
        }
    }
    int64_t total = sj_int(root, "total", -1);
    out->total = total >= 0 ? (uint32_t)total : seen;
    if (out->total < seen) {
        out->total = seen;
    }
    int64_t offset = sj_int(root, "offset", 0);
    out->offset = offset > 0 ? (uint32_t)offset : 0;
    out->has_more = cJSON_IsString(cJSON_GetObjectItemCaseSensitive(root, "next")) || seen > out->count;
    cJSON_Delete(root);
    return SPOTIFY_PARSE_OK;
}
