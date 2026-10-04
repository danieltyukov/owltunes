/* Interactive simulator window. Keys:
 *   Left/Right  turn the ring        Enter  tap        Up  swipe up      Down  back (beak)
 *   n / p       right / left ear     l      like (hold right ear)
 *   w / r       hold / release left ear (preset wheel)
 *   h           hold beak (home)     d      double beak (play/pause)      a  long press
 * Mouse: click = tap, long press = long press, swipe left/right/up = swipes. */
#include <stdio.h>

#include "lvgl.h"
#include "owl_ui.h"
#include "sim_scenarios.h"

static sim_world_t s_world;
static owl_ui_t *s_ui;

static const char *fixture_for(owl_list_kind_t kind)
{
    switch (kind) {
    case OWL_LIST_PLAYLISTS:
        return "playlists.json";
    case OWL_LIST_SAVED_TRACKS:
        return "saved_tracks.json";
    case OWL_LIST_ALBUMS:
        return "albums.json";
    case OWL_LIST_RECENT:
        return "recently_played.json";
    case OWL_LIST_DEVICES:
        return "devices.json";
    case OWL_LIST_PLAYLIST_ITEMS:
        return "playlist_items.json";
    case OWL_LIST_ALBUM_TRACKS:
        return "album_tracks.json";
    default:
        return NULL;
    }
}

static void dispatch(owl_input_kind_t kind, int32_t steps)
{
    owl_effects_t fx;
    owl_input_t in = {kind, steps};
    s_world.now_ms = (int64_t)lv_tick_get();
    owl_app_handle(&s_world.app, &s_world.player, &in, s_world.now_ms, &fx);
    for (uint8_t i = 0; i < fx.n_cmds; i++) {
        printf("command type=%d value=%ld uri=%s\n", (int)fx.cmds[i].type, (long)fx.cmds[i].value, fx.cmds[i].uri);
    }
    if (fx.key != OWL_KEY_NONE) {
        printf("media key %d x%u\n", (int)fx.key, (unsigned)fx.key_repeat);
    }
    if (fx.haptic != OWL_HAPTIC_NONE) {
        printf("haptic %d\n", (int)fx.haptic);
    }
    const char *fixture = fixture_for(fx.fetch.kind);
    if (fixture != NULL) {
        /* Answer the fetch at once from the fixtures, as the network task will on the device. */
        sim_load_list(&s_world, fx.fetch.kind, fixture, fx.fetch.uri[0] ? fx.fetch.uri : NULL);
        if (fx.fetch.kind == OWL_LIST_PLAYLIST_ITEMS || fx.fetch.kind == OWL_LIST_ALBUM_TRACKS) {
            snprintf(s_world.list.source_uri, sizeof s_world.list.source_uri, "%s", fx.fetch.uri);
        }
        printf("fetch %d answered: %u items\n", (int)fx.fetch.kind, (unsigned)s_world.list.count);
        owl_app_set_list(&s_world.app, &s_world.list);
    }
    fflush(stdout);
}

static void key_cb(lv_event_t *e)
{
    switch (lv_event_get_key(e)) {
    case LV_KEY_RIGHT:
        dispatch(OWL_IN_RING, 1);
        break;
    case LV_KEY_LEFT:
        dispatch(OWL_IN_RING, -1);
        break;
    case LV_KEY_ENTER:
        dispatch(OWL_IN_TAP, 0);
        break;
    case LV_KEY_UP:
        dispatch(OWL_IN_SWIPE_UP, 0);
        break;
    case LV_KEY_DOWN:
        dispatch(OWL_IN_BEAK, 0);
        break;
    case 'n':
        dispatch(OWL_IN_EAR_RIGHT, 0);
        break;
    case 'p':
        dispatch(OWL_IN_EAR_LEFT, 0);
        break;
    case 'l':
        dispatch(OWL_IN_EAR_RIGHT_HOLD, 0);
        break;
    case 'w':
        dispatch(OWL_IN_EAR_LEFT_HOLD, 0);
        break;
    case 'r':
        dispatch(OWL_IN_EAR_LEFT_RELEASE, 0);
        break;
    case 'h':
        dispatch(OWL_IN_BEAK_HOLD, 0);
        break;
    case 'd':
        dispatch(OWL_IN_BEAK_DOUBLE, 0);
        break;
    case 'a':
        dispatch(OWL_IN_LONG_PRESS, 0);
        break;
    default:
        break;
    }
}

static void pointer_cb(lv_event_t *e)
{
    /* Enter on the keyboard also produces click events; only react to the mouse here. */
    lv_indev_t *indev = lv_indev_active();
    if (indev == NULL || lv_indev_get_type(indev) != LV_INDEV_TYPE_POINTER) {
        return;
    }
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_SHORT_CLICKED) {
        dispatch(OWL_IN_TAP, 0);
    } else if (code == LV_EVENT_LONG_PRESSED) {
        dispatch(OWL_IN_LONG_PRESS, 0);
    } else if (code == LV_EVENT_GESTURE) {
        lv_dir_t dir = lv_indev_get_gesture_dir(indev);
        if (dir == LV_DIR_LEFT) {
            dispatch(OWL_IN_SWIPE_LEFT, 0);
        } else if (dir == LV_DIR_RIGHT) {
            dispatch(OWL_IN_SWIPE_RIGHT, 0);
        } else if (dir == LV_DIR_TOP) {
            dispatch(OWL_IN_SWIPE_UP, 0);
        }
    }
}

int sim_run_sdl(const char *scenario_name)
{
    const sim_scenario_t *scenario = sim_scenario_find(scenario_name);
    if (scenario == NULL) {
        fprintf(stderr, "unknown scenario: %s\n", scenario_name);
        return 2;
    }
    lv_init();
    lv_display_t *disp = lv_sdl_window_create(OWL_UI_RES, OWL_UI_RES);
    lv_sdl_window_set_title(disp, "OwlTunes simulator");
    lv_sdl_mouse_create();
    lv_indev_t *keyboard = lv_sdl_keyboard_create();

    s_ui = owl_ui_create(disp);
    scenario->setup(&s_world);

    lv_obj_t *screen = lv_screen_active();
    lv_obj_set_clickable(screen, true);
    lv_obj_add_event_cb(screen, pointer_cb, LV_EVENT_ALL, NULL);
    lv_group_t *group = lv_group_create();
    lv_group_add_obj(group, screen);
    lv_indev_set_group(keyboard, group);
    lv_obj_add_event_cb(screen, key_cb, LV_EVENT_KEY, NULL);

    printf("OwlTunes simulator: see the key list at the top of sim/src/sim_sdl.c\n");
    while (true) {
        s_world.now_ms = (int64_t)lv_tick_get();
        owl_ui_render(s_ui, &s_world.app, &s_world.player, &s_world.inputs, s_world.now_ms);
        uint32_t wait = lv_timer_handler();
        lv_delay_ms(wait < 5 ? 5 : (wait > 30 ? 30 : wait));
    }
    return 0;
}
