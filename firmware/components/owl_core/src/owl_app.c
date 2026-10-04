#include "owl_app.h"

#include <string.h>

#include "owl_text.h"

static const char *const LIB_LABELS[OWL_LIB_COUNT] = {
    "Playlists", "Liked Songs", "Albums", "Recently played", "Devices", "Presets",
};

const char *owl_lib_entry_label(owl_lib_entry_t e)
{
    return (unsigned)e < OWL_LIB_COUNT ? LIB_LABELS[e] : "";
}

void owl_app_init(owl_app_t *app)
{
    memset(app, 0, sizeof *app);
    app->depth = 1;
    app->nav[0].screen = OWL_SCREEN_NOW_PLAYING;
    app->link = OWL_LINK_NONE;
}

void owl_app_set_link(owl_app_t *app, owl_link_t link, bool hid_paired)
{
    app->link = link;
    app->hid_paired = hid_paired;
}

const owl_nav_frame_t *owl_app_frame(const owl_app_t *app)
{
    return &app->nav[app->depth - 1];
}

static owl_nav_frame_t *frame(owl_app_t *app)
{
    return &app->nav[app->depth - 1];
}

/* ---- navigation ---------------------------------------------------------------------------- */

static void push(owl_app_t *app, owl_screen_t screen, owl_list_kind_t kind, const char *uri, const char *title)
{
    if (app->depth == OWL_NAV_DEPTH) {
        /* Drop the oldest frame above Now Playing so navigation never fails. */
        memmove(&app->nav[1], &app->nav[2], sizeof(app->nav[0]) * (OWL_NAV_DEPTH - 2));
        app->depth--;
    }
    owl_nav_frame_t *f = &app->nav[app->depth++];
    memset(f, 0, sizeof *f);
    f->screen = screen;
    f->list_kind = kind;
    owl_utf8_copy(f->uri, sizeof f->uri, uri);
    owl_utf8_copy(f->title, sizeof f->title, title);
    if (screen == OWL_SCREEN_BROWSE) {
        app->list = NULL;
    }
}

static void request(owl_effects_t *fx, owl_list_kind_t kind, const char *uri)
{
    fx->fetch.kind = kind;
    owl_utf8_copy(fx->fetch.uri, sizeof fx->fetch.uri, uri);
    fx->fetch.offset = 0;
}

static void open_list(owl_app_t *app, owl_effects_t *fx, owl_list_kind_t kind, const char *uri, const char *title)
{
    push(app, OWL_SCREEN_BROWSE, kind, uri, title);
    request(fx, kind, uri);
    fx->haptic = OWL_HAPTIC_CONFIRM;
}

static void back(owl_app_t *app, owl_effects_t *fx)
{
    if (app->depth <= 1) {
        return;
    }
    if (frame(app)->screen == OWL_SCREEN_PRESETS) {
        app->wheel_open = false;
    }
    app->depth--;
    const owl_nav_frame_t *f = frame(app);
    if (f->screen == OWL_SCREEN_BROWSE) {
        /* The previous page may have been replaced; ask for it again (the data layer caches). */
        app->list = NULL;
        request(fx, f->list_kind, f->uri);
    }
    fx->haptic = OWL_HAPTIC_TICK;
}

static void home(owl_app_t *app)
{
    app->depth = 1;
    app->wheel_open = false;
    app->list = NULL;
}

/* ---- effects --------------------------------------------------------------------------------- */

static owl_cmd_t *emit(owl_effects_t *fx, owl_cmd_type_t type, int32_t value, const char *uri)
{
    if (fx->n_cmds == OWL_EFFECTS_MAX_CMDS) {
        return NULL;
    }
    owl_cmd_t *c = &fx->cmds[fx->n_cmds++];
    owl_cmd_set(c, type, value, uri);
    return c;
}

static void send_key(owl_effects_t *fx, owl_media_key_t key, uint32_t repeat)
{
    fx->key = key;
    fx->key_repeat = (uint8_t)(repeat > 255 ? 255 : repeat);
}

static bool can_command(const owl_app_t *app, const owl_player_t *p)
{
    return app->link == OWL_LINK_API && p->has_device && !p->device.is_restricted &&
           p->status != OWL_PLAYER_NO_DEVICE;
}

/* ---- transport ------------------------------------------------------------------------------- */

static void toggle_play(owl_app_t *app, owl_player_t *p, owl_effects_t *fx)
{
    if (app->link == OWL_LINK_BLE) {
        send_key(fx, OWL_KEY_PLAY_PAUSE, 1);
        fx->haptic = OWL_HAPTIC_CONFIRM;
        return;
    }
    if (!can_command(app, p)) {
        fx->haptic = OWL_HAPTIC_BUZZ;
        return;
    }
    emit(fx, p->status == OWL_PLAYER_PLAYING ? OWL_CMD_PAUSE : OWL_CMD_PLAY, 0, NULL);
    fx->haptic = OWL_HAPTIC_CONFIRM;
}

static void skip(owl_app_t *app, owl_player_t *p, owl_effects_t *fx, bool forward)
{
    if (app->link == OWL_LINK_BLE) {
        send_key(fx, forward ? OWL_KEY_NEXT : OWL_KEY_PREV, 1);
        fx->haptic = OWL_HAPTIC_TICK;
        return;
    }
    if (!can_command(app, p)) {
        fx->haptic = OWL_HAPTIC_BUZZ;
        return;
    }
    emit(fx, forward ? OWL_CMD_NEXT : OWL_CMD_PREV, 0, NULL);
    fx->haptic = OWL_HAPTIC_TICK;
}

static void toggle_like(owl_app_t *app, owl_player_t *p, owl_effects_t *fx)
{
    if (app->link != OWL_LINK_API || !p->has_track || p->track.kind != OWL_ITEM_TRACK ||
        strncmp(p->track.uri, "spotify:track:", 14) != 0) {
        fx->haptic = OWL_HAPTIC_BUZZ;
        return;
    }
    emit(fx, p->liked ? OWL_CMD_UNLIKE : OWL_CMD_LIKE, 0, p->track.uri);
    fx->haptic = OWL_HAPTIC_HEARTBEAT;
}

static void ring_now_playing(owl_app_t *app, owl_player_t *p, int32_t steps, int64_t now, owl_effects_t *fx)
{
    bool api_volume = can_command(app, p) && p->device.supports_volume;
    if (!api_volume && app->hid_paired && app->link != OWL_LINK_NONE) {
        send_key(fx, steps > 0 ? OWL_KEY_VOL_UP : OWL_KEY_VOL_DOWN, (uint32_t)(steps > 0 ? steps : -steps));
        fx->haptic = OWL_HAPTIC_TICK;
        return;
    }
    if (!can_command(app, p)) {
        fx->haptic = OWL_HAPTIC_BUZZ;
        return;
    }
    if (!p->device.supports_volume) {
        /* The device refuses volume changes and no media-key link exists: seek instead. */
        int64_t target = (int64_t)owl_player_progress_now(p, now) + (int64_t)steps * OWL_SEEK_STEP_MS;
        if (target < 0) {
            target = 0;
        }
        if (p->track.duration_ms > 0 && target > p->track.duration_ms) {
            target = p->track.duration_ms;
        }
        emit(fx, OWL_CMD_SEEK, (int32_t)target, NULL);
        fx->haptic = OWL_HAPTIC_TICK;
        return;
    }
    int32_t current = p->device.volume_percent < 0 ? 50 : p->device.volume_percent;
    int32_t target = current + steps * OWL_VOLUME_STEP;
    bool clamped = target < 0 || target > 100;
    target = target < 0 ? 0 : (target > 100 ? 100 : target);
    app->volume_overlay_until_ms = now + OWL_VOLUME_OVERLAY_MS;
    if (target == current) {
        fx->haptic = OWL_HAPTIC_BUMP;
        return;
    }
    emit(fx, OWL_CMD_VOLUME, target, NULL);
    fx->haptic = clamped ? OWL_HAPTIC_BUMP : OWL_HAPTIC_TICK;
}

/* ---- lists ----------------------------------------------------------------------------------- */

static int16_t list_count(const owl_app_t *app)
{
    const owl_nav_frame_t *f = owl_app_frame(app);
    if (f->screen == OWL_SCREEN_LIBRARY) {
        return OWL_LIB_COUNT;
    }
    if (f->screen == OWL_SCREEN_BROWSE && app->list != NULL) {
        return (int16_t)app->list->count;
    }
    return 0;
}

static void move_cursor(owl_app_t *app, int32_t steps, owl_effects_t *fx)
{
    owl_nav_frame_t *f = frame(app);
    int16_t count = list_count(app);
    if (count == 0) {
        fx->haptic = OWL_HAPTIC_BUMP;
        return;
    }
    int32_t target = f->cursor + steps;
    bool clamped = target < 0 || target >= count;
    target = target < 0 ? 0 : (target >= count ? count - 1 : target);
    bool moved = target != f->cursor;
    f->cursor = (int16_t)target;
    fx->haptic = clamped ? OWL_HAPTIC_BUMP : (moved ? OWL_HAPTIC_TICK : OWL_HAPTIC_NONE);
}

static void play_context(owl_app_t *app, owl_player_t *p, owl_effects_t *fx, const char *context,
                         const char *offset_uri, const char *name)
{
    if (!can_command(app, p)) {
        fx->haptic = OWL_HAPTIC_BUZZ;
        return;
    }
    owl_cmd_t *c = emit(fx, OWL_CMD_PLAY_CONTEXT, 0, context);
    if (c != NULL && offset_uri != NULL) {
        owl_utf8_copy(c->offset_uri, sizeof c->offset_uri, offset_uri);
    }
    owl_utf8_copy(p->context_name, sizeof p->context_name, name);
    home(app);
    fx->haptic = OWL_HAPTIC_CONFIRM;
}

static void play_uris(owl_app_t *app, owl_player_t *p, owl_effects_t *fx, const owl_list_page_t *list,
                      int16_t start)
{
    if (!can_command(app, p)) {
        fx->haptic = OWL_HAPTIC_BUZZ;
        return;
    }
    owl_cmd_t *c = emit(fx, OWL_CMD_PLAY_URIS, 0, NULL);
    if (c == NULL) {
        return;
    }
    for (int16_t i = start; i < (int16_t)list->count && c->n_uris < OWL_CMD_MAX_URIS; i++) {
        if (!list->items[i].disabled) {
            owl_utf8_copy(c->uris[c->n_uris++], OWL_URI_LEN, list->items[i].uri);
        }
    }
    owl_utf8_copy(p->context_name, sizeof p->context_name, NULL);
    home(app);
    fx->haptic = OWL_HAPTIC_CONFIRM;
}

static void select_library(owl_app_t *app, owl_effects_t *fx)
{
    switch ((owl_lib_entry_t)frame(app)->cursor) {
    case OWL_LIB_PLAYLISTS:
        open_list(app, fx, OWL_LIST_PLAYLISTS, NULL, NULL);
        break;
    case OWL_LIB_LIKED:
        open_list(app, fx, OWL_LIST_SAVED_TRACKS, NULL, NULL);
        break;
    case OWL_LIB_ALBUMS:
        open_list(app, fx, OWL_LIST_ALBUMS, NULL, NULL);
        break;
    case OWL_LIB_RECENT:
        open_list(app, fx, OWL_LIST_RECENT, NULL, NULL);
        break;
    case OWL_LIB_DEVICES:
        open_list(app, fx, OWL_LIST_DEVICES, NULL, NULL);
        break;
    case OWL_LIB_PRESETS:
        push(app, OWL_SCREEN_PRESETS, OWL_LIST_NONE, NULL, NULL);
        fx->haptic = OWL_HAPTIC_CONFIRM;
        break;
    default:
        fx->haptic = OWL_HAPTIC_BUZZ;
        break;
    }
}

static void select_browse(owl_app_t *app, owl_player_t *p, owl_effects_t *fx)
{
    const owl_list_page_t *list = app->list;
    int16_t cursor = frame(app)->cursor;
    if (list == NULL || cursor < 0 || cursor >= (int16_t)list->count || list->items[cursor].disabled) {
        fx->haptic = OWL_HAPTIC_BUZZ;
        return;
    }
    const owl_list_item_t *it = &list->items[cursor];
    switch (list->kind) {
    case OWL_LIST_PLAYLISTS:
        if (it->browsable) {
            open_list(app, fx, OWL_LIST_PLAYLIST_ITEMS, it->uri, it->title);
        } else {
            play_context(app, p, fx, it->uri, NULL, it->title);
        }
        break;
    case OWL_LIST_ALBUMS:
        open_list(app, fx, OWL_LIST_ALBUM_TRACKS, it->uri, it->title);
        break;
    case OWL_LIST_PLAYLIST_ITEMS:
    case OWL_LIST_ALBUM_TRACKS:
        play_context(app, p, fx, list->source_uri, it->uri, frame(app)->title);
        break;
    case OWL_LIST_SAVED_TRACKS:
    case OWL_LIST_RECENT:
        play_uris(app, p, fx, list, cursor);
        break;
    case OWL_LIST_DEVICES:
        if (app->link != OWL_LINK_API) {
            fx->haptic = OWL_HAPTIC_BUZZ;
            break;
        }
        emit(fx, OWL_CMD_TRANSFER, 0, it->uri);
        home(app);
        fx->haptic = OWL_HAPTIC_CONFIRM;
        break;
    default:
        fx->haptic = OWL_HAPTIC_BUZZ;
        break;
    }
}

/* ---- presets --------------------------------------------------------------------------------- */

static void open_wheel(owl_app_t *app, owl_effects_t *fx)
{
    if (app->wheel_open) {
        return;
    }
    push(app, OWL_SCREEN_PRESETS, OWL_LIST_NONE, NULL, NULL);
    app->wheel_open = true;
    fx->haptic = OWL_HAPTIC_PRESET;
}

static void move_preset(owl_app_t *app, int32_t steps, owl_effects_t *fx)
{
    int32_t n = ((int32_t)app->preset_cursor + steps) % OWL_PRESET_COUNT;
    if (n < 0) {
        n += OWL_PRESET_COUNT;
    }
    app->preset_cursor = (uint8_t)n;
    fx->haptic = OWL_HAPTIC_PRESET;
}

static void play_preset(owl_app_t *app, owl_player_t *p, owl_effects_t *fx)
{
    const owl_preset_t *pr = &app->presets[app->preset_cursor];
    if (!pr->assigned) {
        fx->haptic = OWL_HAPTIC_BUZZ;
        return;
    }
    play_context(app, p, fx, pr->uri, NULL, pr->label);
}

static void release_wheel(owl_app_t *app, owl_player_t *p, owl_effects_t *fx)
{
    if (!app->wheel_open) {
        return;
    }
    app->wheel_open = false;
    if (app->depth > 1) {
        app->depth--; /* close the wheel frame before acting */
    }
    play_preset(app, p, fx);
}

static void assign_preset(owl_app_t *app, const owl_player_t *p, owl_effects_t *fx)
{
    if (p->context_uri[0] == '\0') {
        fx->haptic = OWL_HAPTIC_BUZZ;
        return;
    }
    owl_preset_t *pr = &app->presets[app->preset_cursor];
    pr->assigned = true;
    owl_utf8_copy(pr->uri, sizeof pr->uri, p->context_uri);
    const char *label = p->context_name[0] ? p->context_name : (p->has_track ? p->track.album : "");
    owl_utf8_copy(pr->label, sizeof pr->label, label[0] ? label : "Preset");
    fx->haptic = OWL_HAPTIC_CONFIRM;
}

/* ---- input dispatch -------------------------------------------------------------------------- */

void owl_app_handle(owl_app_t *app, owl_player_t *player, const owl_input_t *in, int64_t now_ms,
                    owl_effects_t *fx)
{
    memset(fx, 0, sizeof *fx);
    owl_screen_t screen = owl_app_frame(app)->screen;

    switch (in->kind) {
    /* Physical buttons behave the same on every screen so they can be used without looking. */
    case OWL_IN_EAR_LEFT:
        skip(app, player, fx, false);
        break;
    case OWL_IN_EAR_RIGHT:
        skip(app, player, fx, true);
        break;
    case OWL_IN_EAR_RIGHT_HOLD:
        toggle_like(app, player, fx);
        break;
    case OWL_IN_EAR_LEFT_HOLD:
        open_wheel(app, fx);
        break;
    case OWL_IN_EAR_LEFT_RELEASE:
        release_wheel(app, player, fx);
        break;
    case OWL_IN_BEAK:
        back(app, fx);
        break;
    case OWL_IN_BEAK_HOLD:
        home(app);
        fx->haptic = OWL_HAPTIC_CONFIRM;
        break;
    case OWL_IN_BEAK_DOUBLE:
        toggle_play(app, player, fx);
        break;
    case OWL_IN_RING:
        if (app->ring_locked || in->steps == 0) {
            break;
        }
        if (screen == OWL_SCREEN_PRESETS) {
            move_preset(app, in->steps, fx);
        } else if (screen == OWL_SCREEN_NOW_PLAYING) {
            ring_now_playing(app, player, in->steps, now_ms, fx);
        } else {
            move_cursor(app, in->steps, fx);
        }
        break;
    case OWL_IN_TAP:
        if (screen == OWL_SCREEN_NOW_PLAYING) {
            if (app->link == OWL_LINK_API && player->status == OWL_PLAYER_NO_DEVICE) {
                open_list(app, fx, OWL_LIST_DEVICES, NULL, NULL);
            } else {
                toggle_play(app, player, fx);
            }
        } else if (screen == OWL_SCREEN_LIBRARY) {
            select_library(app, fx);
        } else if (screen == OWL_SCREEN_BROWSE) {
            select_browse(app, player, fx);
        } else if (!app->wheel_open) {
            play_preset(app, player, fx);
        }
        break;
    case OWL_IN_LONG_PRESS:
        if (screen == OWL_SCREEN_PRESETS && !app->wheel_open) {
            assign_preset(app, player, fx);
        }
        break;
    case OWL_IN_SWIPE_LEFT:
        if (screen == OWL_SCREEN_NOW_PLAYING) {
            skip(app, player, fx, true);
        }
        break;
    case OWL_IN_SWIPE_RIGHT:
        if (screen == OWL_SCREEN_NOW_PLAYING) {
            skip(app, player, fx, false);
        } else {
            back(app, fx);
        }
        break;
    case OWL_IN_SWIPE_UP:
        if (screen != OWL_SCREEN_NOW_PLAYING) {
            break;
        }
        if (app->link == OWL_LINK_API) {
            push(app, OWL_SCREEN_LIBRARY, OWL_LIST_NONE, NULL, NULL);
            fx->haptic = OWL_HAPTIC_CONFIRM;
        } else {
            fx->haptic = OWL_HAPTIC_BUZZ;
        }
        break;
    }

    for (uint8_t i = 0; i < fx->n_cmds; i++) {
        owl_player_apply_optimistic(player, &fx->cmds[i], now_ms);
    }
}

bool owl_app_set_list(owl_app_t *app, const owl_list_page_t *page)
{
    owl_nav_frame_t *f = frame(app);
    if (page == NULL || f->screen != OWL_SCREEN_BROWSE || page->kind != f->list_kind) {
        return false;
    }
    if (f->uri[0] != '\0' && strcmp(f->uri, page->source_uri) != 0) {
        return false;
    }
    app->list = page;
    if (f->cursor >= (int16_t)page->count) {
        f->cursor = page->count > 0 ? (int16_t)(page->count - 1) : 0;
    }
    return true;
}
