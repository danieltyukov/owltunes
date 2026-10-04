#include <string.h>

#include "owl_text.h"
#include "spotify_json.h"
#include "spotify_parse.h"

static void parse_device(const cJSON *dev, owl_device_t *d)
{
    owl_utf8_copy(d->id, sizeof d->id, sj_str(dev, "id"));
    owl_utf8_copy(d->name, sizeof d->name, sj_str(dev, "name"));
    owl_utf8_copy(d->type, sizeof d->type, sj_str(dev, "type"));
    d->is_active = sj_bool(dev, "is_active", false);
    d->is_restricted = sj_bool(dev, "is_restricted", false);
    d->supports_volume = sj_bool(dev, "supports_volume", true);
    int64_t volume = sj_int(dev, "volume_percent", -1);
    d->volume_percent = (int8_t)(volume < 0 ? -1 : (volume > 100 ? 100 : volume));
}

spotify_parse_result_t spotify_parse_player(const char *json, size_t len, int64_t now_ms, owl_player_t *out)
{
    if (json == NULL || len == 0) {
        owl_player_init(out);
        out->status = OWL_PLAYER_NO_DEVICE;
        return SPOTIFY_PARSE_OK;
    }
    cJSON *root = cJSON_ParseWithLength(json, len);
    if (root == NULL) {
        return SPOTIFY_PARSE_BAD_JSON;
    }
    if (!cJSON_IsObject(root)) {
        cJSON_Delete(root);
        return SPOTIFY_PARSE_BAD_SHAPE;
    }

    /* Keep what the poll does not report, so it survives when nothing changed. */
    char old_track[OWL_URI_LEN], old_context[OWL_URI_LEN], old_context_name[OWL_NAME_LEN];
    bool old_has_track = out->has_track, old_liked = out->liked, old_liked_known = out->liked_known;
    owl_utf8_copy(old_track, sizeof old_track, out->track.uri);
    owl_utf8_copy(old_context, sizeof old_context, out->context_uri);
    owl_utf8_copy(old_context_name, sizeof old_context_name, out->context_name);

    owl_player_init(out);
    const cJSON *dev = sj_obj(root, "device");
    if (dev != NULL) {
        out->has_device = true;
        parse_device(dev, &out->device);
    }
    bool playing = sj_bool(root, "is_playing", false);
    out->status = dev == NULL ? OWL_PLAYER_NO_DEVICE : (playing ? OWL_PLAYER_PLAYING : OWL_PLAYER_PAUSED);
    out->shuffle = sj_bool(root, "shuffle_state", false);
    const char *repeat = sj_str(root, "repeat_state");
    if (repeat != NULL && strcmp(repeat, "track") == 0) {
        out->repeat = OWL_REPEAT_TRACK;
    } else if (repeat != NULL && strcmp(repeat, "context") == 0) {
        out->repeat = OWL_REPEAT_CONTEXT;
    }
    const cJSON *context = sj_obj(root, "context");
    if (context != NULL) {
        owl_utf8_copy(out->context_uri, sizeof out->context_uri, sj_str(context, "uri"));
    }
    const cJSON *item = sj_obj(root, "item");
    const char *playing_type = sj_str(root, "currently_playing_type");
    if (item != NULL) {
        sj_parse_track(item, &out->track);
        out->has_track = true;
    } else if (playing_type != NULL && strcmp(playing_type, "ad") == 0) {
        out->track.kind = OWL_ITEM_AD;
    }
    int64_t progress = sj_int(root, "progress_ms", 0);
    if (progress < 0) {
        progress = 0;
    }
    if (out->has_track && out->track.duration_ms > 0 && progress > out->track.duration_ms) {
        progress = out->track.duration_ms;
    }
    out->progress_ms = (uint32_t)progress;
    out->progress_at_ms = now_ms;

    if (out->has_track && old_has_track && strcmp(old_track, out->track.uri) == 0) {
        out->liked = old_liked;
        out->liked_known = old_liked_known;
    }
    if (out->context_uri[0] != '\0' && strcmp(old_context, out->context_uri) == 0) {
        owl_utf8_copy(out->context_name, sizeof out->context_name, old_context_name);
    }
    cJSON_Delete(root);
    return SPOTIFY_PARSE_OK;
}

void spotify_classify_error(int http_status, const char *body, size_t len, int32_t retry_after_s,
                            spotify_error_t *out)
{
    memset(out, 0, sizeof *out);
    out->http_status = http_status;
    out->retry_after_s = retry_after_s;
    if (http_status >= 200 && http_status < 300) {
        out->kind = SPOTIFY_ERROR_NONE;
        return;
    }
    char reason[48] = "";
    if (body != NULL && len > 0) {
        cJSON *root = cJSON_ParseWithLength(body, len);
        const cJSON *err = root ? sj_obj(root, "error") : NULL;
        if (err != NULL) {
            owl_utf8_copy(reason, sizeof reason, sj_str(err, "reason"));
            owl_utf8_copy(out->message, sizeof out->message, sj_str(err, "message"));
        }
        cJSON_Delete(root);
    }
    if (http_status == 401) {
        out->kind = SPOTIFY_ERROR_AUTH_EXPIRED;
    } else if (http_status == 429) {
        out->kind = strcmp(reason, "QUOTA_EXCEEDED") == 0 ? SPOTIFY_ERROR_QUOTA_EXCEEDED : SPOTIFY_ERROR_RATE_LIMITED;
        if (out->retry_after_s <= 0) {
            out->retry_after_s = 5;
        }
    } else if (http_status == 404) {
        bool no_device = strcmp(reason, "NO_ACTIVE_DEVICE") == 0 || strstr(out->message, "No active device") != NULL;
        out->kind = no_device ? SPOTIFY_ERROR_NO_ACTIVE_DEVICE : SPOTIFY_ERROR_NOT_FOUND;
    } else if (http_status == 403) {
        out->kind = strcmp(reason, "PREMIUM_REQUIRED") == 0 ? SPOTIFY_ERROR_PREMIUM_REQUIRED : SPOTIFY_ERROR_FORBIDDEN;
    } else if (http_status >= 500) {
        out->kind = SPOTIFY_ERROR_SERVER;
    } else {
        out->kind = SPOTIFY_ERROR_OTHER;
    }
}
