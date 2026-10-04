#include "spotify_json.h"

#include <stdlib.h>
#include <string.h>

#include "owl_text.h"

const char *sj_str(const cJSON *obj, const char *key)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsString(v) ? v->valuestring : NULL;
}

bool sj_bool(const cJSON *obj, const char *key, bool fallback)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsBool(v) ? cJSON_IsTrue(v) : fallback;
}

int64_t sj_int(const cJSON *obj, const char *key, int64_t fallback)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsNumber(v) ? (int64_t)v->valuedouble : fallback;
}

const cJSON *sj_obj(const cJSON *obj, const char *key)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsObject(v) ? v : NULL;
}

const cJSON *sj_arr(const cJSON *obj, const char *key)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(obj, key);
    return cJSON_IsArray(v) ? v : NULL;
}

const char *sj_pick_image(const cJSON *images, int want_px)
{
    const char *best = "";
    int64_t best_diff = INT64_MAX;
    int64_t best_width = -1;
    const cJSON *img;
    cJSON_ArrayForEach(img, images)
    {
        const char *url = sj_str(img, "url");
        if (url == NULL) {
            continue;
        }
        int64_t width = sj_int(img, "width", 0);
        int64_t diff = llabs(width - want_px);
        if (diff < best_diff || (diff == best_diff && width > best_width)) {
            best = url;
            best_diff = diff;
            best_width = width;
        }
    }
    return best;
}

void sj_join_names(const cJSON *artists, char *dst, size_t cap)
{
    if (cap == 0) {
        return;
    }
    dst[0] = '\0';
    bool first = true;
    const cJSON *a;
    cJSON_ArrayForEach(a, artists)
    {
        const char *name = sj_str(a, "name");
        if (name == NULL || name[0] == '\0') {
            continue;
        }
        if (!first) {
            if (strlen(dst) + 3 >= cap) {
                break; /* no room for ", " and at least one more byte */
            }
            owl_utf8_append(dst, cap, ", ");
        }
        owl_utf8_append(dst, cap, name);
        first = false;
    }
}

void sj_parse_track(const cJSON *item, owl_track_t *t)
{
    memset(t, 0, sizeof *t);
    const char *type = sj_str(item, "type");
    owl_utf8_copy(t->uri, sizeof t->uri, sj_str(item, "uri"));
    owl_utf8_copy(t->title, sizeof t->title, sj_str(item, "name"));
    int64_t duration = sj_int(item, "duration_ms", 0);
    t->duration_ms = duration > 0 ? (uint32_t)duration : 0;
    if (type != NULL && strcmp(type, "episode") == 0) {
        t->kind = OWL_ITEM_EPISODE;
        const cJSON *show = sj_obj(item, "show");
        owl_utf8_copy(t->subtitle, sizeof t->subtitle, show ? sj_str(show, "name") : NULL);
        const cJSON *images = sj_arr(item, "images");
        if (images == NULL && show != NULL) {
            images = sj_arr(show, "images");
        }
        owl_utf8_copy(t->art_url, sizeof t->art_url, sj_pick_image(images, 300));
        return;
    }
    t->kind = (type == NULL || strcmp(type, "track") == 0) ? OWL_ITEM_TRACK : OWL_ITEM_UNKNOWN;
    if (sj_bool(item, "is_local", false)) {
        t->kind = OWL_ITEM_UNKNOWN; /* local files cannot be liked, queued or played by URI */
    }
    sj_join_names(sj_arr(item, "artists"), t->subtitle, sizeof t->subtitle);
    const cJSON *album = sj_obj(item, "album");
    if (album != NULL) {
        owl_utf8_copy(t->album, sizeof t->album, sj_str(album, "name"));
        owl_utf8_copy(t->art_url, sizeof t->art_url, sj_pick_image(sj_arr(album, "images"), 300));
    }
}
