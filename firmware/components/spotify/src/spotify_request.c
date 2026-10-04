#include "spotify_api.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "owl_text.h"

const char *spotify_method_name(spotify_method_t m)
{
    switch (m) {
    case SPOTIFY_GET:
        return "GET";
    case SPOTIFY_PUT:
        return "PUT";
    case SPOTIFY_POST:
        return "POST";
    case SPOTIFY_DELETE:
        return "DELETE";
    }
    return "GET";
}

/* Spotify URIs, ids and device ids only ever use these characters. Anything else is refused so
 * it can never break out of a query string or a JSON string. */
static bool safe_token(const char *s)
{
    if (s == NULL || *s == '\0') {
        return false;
    }
    for (; *s; s++) {
        char c = *s;
        bool ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == ':' ||
                  c == '.' || c == '_' || c == '-';
        if (!ok) {
            return false;
        }
    }
    return true;
}

__attribute__((format(printf, 3, 4))) static bool set_path(spotify_request_t *out, spotify_method_t method,
                                                             const char *fmt, ...)
{
    out->method = method;
    va_list args;
    va_start(args, fmt);
    int n = vsnprintf(out->path, sizeof out->path, fmt, args);
    va_end(args);
    return n > 0 && (size_t)n < sizeof out->path;
}

__attribute__((format(printf, 2, 3))) static bool set_body(spotify_request_t *out, const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    int n = vsnprintf(out->body, sizeof out->body, fmt, args);
    va_end(args);
    return n > 0 && (size_t)n < sizeof out->body;
}

static bool uri_query(spotify_request_t *out, spotify_method_t method, const char *path_prefix, const char *uri)
{
    char enc[3 * OWL_URI_LEN];
    if (!safe_token(uri) || owl_url_encode(enc, sizeof enc, uri) == OWL_TEXT_OVERFLOW) {
        return false;
    }
    return set_path(out, method, "%s%s", path_prefix, enc);
}

static bool play_uris_body(spotify_request_t *out, const owl_cmd_t *cmd)
{
    if (cmd->n_uris == 0 || cmd->n_uris > OWL_CMD_MAX_URIS) {
        return false;
    }
    size_t used = 0;
    int n = snprintf(out->body, sizeof out->body, "{\"uris\":[");
    used = (size_t)n;
    for (uint8_t i = 0; i < cmd->n_uris; i++) {
        if (!safe_token(cmd->uris[i])) {
            return false;
        }
        n = snprintf(out->body + used, sizeof out->body - used, "%s\"%s\"", i ? "," : "", cmd->uris[i]);
        if (n < 0 || (size_t)n >= sizeof out->body - used) {
            return false;
        }
        used += (size_t)n;
    }
    n = snprintf(out->body + used, sizeof out->body - used, "]}");
    return n > 0 && (size_t)n < sizeof out->body - used;
}

bool spotify_request_for_command(const owl_cmd_t *cmd, spotify_request_t *out)
{
    static const char *const repeat_states[] = {"off", "context", "track"};
    memset(out, 0, sizeof *out);
    switch (cmd->type) {
    case OWL_CMD_PLAY:
        return set_path(out, SPOTIFY_PUT, "/v1/me/player/play");
    case OWL_CMD_PAUSE:
        return set_path(out, SPOTIFY_PUT, "/v1/me/player/pause");
    case OWL_CMD_NEXT:
        return set_path(out, SPOTIFY_POST, "/v1/me/player/next");
    case OWL_CMD_PREV:
        return set_path(out, SPOTIFY_POST, "/v1/me/player/previous");
    case OWL_CMD_SEEK:
        return cmd->value >= 0 && set_path(out, SPOTIFY_PUT, "/v1/me/player/seek?position_ms=%ld", (long)cmd->value);
    case OWL_CMD_VOLUME:
        return cmd->value >= 0 && cmd->value <= 100 &&
               set_path(out, SPOTIFY_PUT, "/v1/me/player/volume?volume_percent=%ld", (long)cmd->value);
    case OWL_CMD_SHUFFLE:
        return set_path(out, SPOTIFY_PUT, "/v1/me/player/shuffle?state=%s", cmd->value ? "true" : "false");
    case OWL_CMD_REPEAT:
        if (cmd->value < 0 || cmd->value > 2) {
            return false;
        }
        return set_path(out, SPOTIFY_PUT, "/v1/me/player/repeat?state=%s", repeat_states[cmd->value]);
    case OWL_CMD_LIKE:
        /* https://developer.spotify.com/documentation/web-api/reference/save-library-items */
        return uri_query(out, SPOTIFY_PUT, "/v1/me/library?uris=", cmd->uri);
    case OWL_CMD_UNLIKE:
        return uri_query(out, SPOTIFY_DELETE, "/v1/me/library?uris=", cmd->uri);
    case OWL_CMD_QUEUE_ADD:
        return uri_query(out, SPOTIFY_POST, "/v1/me/player/queue?uri=", cmd->uri);
    case OWL_CMD_PLAY_CONTEXT:
        if (!safe_token(cmd->uri) || (cmd->offset_uri[0] && !safe_token(cmd->offset_uri))) {
            return false;
        }
        if (!set_path(out, SPOTIFY_PUT, "/v1/me/player/play")) {
            return false;
        }
        if (cmd->offset_uri[0]) {
            return set_body(out, "{\"context_uri\":\"%s\",\"offset\":{\"uri\":\"%s\"}}", cmd->uri, cmd->offset_uri);
        }
        return set_body(out, "{\"context_uri\":\"%s\"}", cmd->uri);
    case OWL_CMD_PLAY_URIS:
        return set_path(out, SPOTIFY_PUT, "/v1/me/player/play") && play_uris_body(out, cmd);
    case OWL_CMD_TRANSFER:
        return safe_token(cmd->uri) && set_path(out, SPOTIFY_PUT, "/v1/me/player") &&
               set_body(out, "{\"device_ids\":[\"%s\"],\"play\":true}", cmd->uri);
    case OWL_CMD_NONE:
        return false;
    }
    return false;
}

/* Extract the id from "spotify:<type>:<id>". */
static bool uri_id(const char *uri, const char *type, char *id, size_t cap)
{
    char prefix[32];
    snprintf(prefix, sizeof prefix, "spotify:%s:", type);
    size_t plen = strlen(prefix);
    if (strncmp(uri, prefix, plen) != 0 || !safe_token(uri + plen) || strchr(uri + plen, ':') != NULL) {
        return false;
    }
    return owl_utf8_copy(id, cap, uri + plen) == strlen(uri + plen);
}

bool spotify_request_for_fetch(const owl_fetch_t *fetch, spotify_request_t *out)
{
    char id[OWL_URI_LEN];
    unsigned long offset = (unsigned long)fetch->offset;
    memset(out, 0, sizeof *out);
    switch (fetch->kind) {
    case OWL_LIST_PLAYLISTS:
        return set_path(out, SPOTIFY_GET, "/v1/me/playlists?limit=50&offset=%lu", offset);
    case OWL_LIST_SAVED_TRACKS:
        return set_path(out, SPOTIFY_GET, "/v1/me/tracks?limit=50&offset=%lu", offset);
    case OWL_LIST_ALBUMS:
        return set_path(out, SPOTIFY_GET, "/v1/me/albums?limit=50&offset=%lu", offset);
    case OWL_LIST_RECENT:
        return set_path(out, SPOTIFY_GET, "/v1/me/player/recently-played?limit=50");
    case OWL_LIST_QUEUE:
        return set_path(out, SPOTIFY_GET, "/v1/me/player/queue");
    case OWL_LIST_DEVICES:
        return set_path(out, SPOTIFY_GET, "/v1/me/player/devices");
    case OWL_LIST_PLAYLIST_ITEMS:
        return uri_id(fetch->uri, "playlist", id, sizeof id) &&
               set_path(out, SPOTIFY_GET, "/v1/playlists/%s/items?limit=50&offset=%lu&additional_types=episode", id,
                        offset);
    case OWL_LIST_ALBUM_TRACKS:
        return uri_id(fetch->uri, "album", id, sizeof id) &&
               set_path(out, SPOTIFY_GET, "/v1/albums/%s/tracks?limit=50&offset=%lu", id, offset);
    case OWL_LIST_NONE:
        return false;
    }
    return false;
}

void spotify_request_player_state(spotify_request_t *out)
{
    memset(out, 0, sizeof *out);
    set_path(out, SPOTIFY_GET, "/v1/me/player?additional_types=episode");
}
