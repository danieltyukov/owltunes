#include <stdio.h>

#include "owl_ui_internal.h"

#define ART_SIZE 216
#define ART_Y (-52)
#define RING_WIDTH 8

void owl_np_create(owl_np_page_t *pg, lv_obj_t *parent)
{
    pg->root = owl_ui_page(parent);
    pg->progress = owl_ui_ring(pg->root, RING_WIDTH, OWL_COLOR_BARK, OWL_COLOR_CREAM);
    pg->volume = owl_ui_ring(pg->root, RING_WIDTH, OWL_COLOR_BARK, OWL_COLOR_AMBER);
    lv_arc_set_range(pg->volume, 0, 100);

    pg->art_placeholder = owl_ui_box(pg->root, ART_SIZE, ART_SIZE, OWL_COLOR_BARK, 4);
    lv_obj_align(pg->art_placeholder, LV_ALIGN_CENTER, 0, ART_Y);
    lv_obj_t *note = owl_ui_label(pg->art_placeholder, &lv_font_montserrat_40, OWL_COLOR_DIM, 0);
    lv_label_set_text(note, LV_SYMBOL_AUDIO);
    lv_obj_center(note);

    pg->art = lv_image_create(pg->root);
    lv_obj_set_size(pg->art, ART_SIZE, ART_SIZE);
    lv_obj_align(pg->art, LV_ALIGN_CENTER, 0, ART_Y);
    lv_obj_set_style_radius(pg->art, 4, 0);
    lv_obj_set_style_clip_corner(pg->art, true, 0);
    lv_obj_set_clickable(pg->art, false);

    pg->title = owl_ui_label(pg->root, &owl_font_28, OWL_COLOR_CREAM, 320);
    lv_obj_align(pg->title, LV_ALIGN_CENTER, 0, 84);
    pg->liked = owl_ui_box(pg->root, 10, 10, OWL_COLOR_AMBER, LV_RADIUS_CIRCLE);
    lv_obj_align(pg->liked, LV_ALIGN_CENTER, -172, 84);
    pg->subtitle = owl_ui_label(pg->root, &owl_font_20, OWL_COLOR_MUTED, 300);
    lv_obj_align(pg->subtitle, LV_ALIGN_CENTER, 0, 120);
    /* Placeholder for the official Spotify logo (at least 70 px wide), which replaces this label
     * when the brand assets are added before release. See docs/design section 5. */
    pg->brand = owl_ui_label(pg->root, &owl_font_14, OWL_COLOR_MUTED, 0);
    lv_label_set_text(pg->brand, "Spotify");
    lv_obj_align(pg->brand, LV_ALIGN_CENTER, 0, 158);
    pg->status = owl_ui_label(pg->root, &owl_font_14, OWL_COLOR_MUTED, 0);
    lv_obj_align(pg->status, LV_ALIGN_CENTER, 0, -196);

    pg->eyes = owl_eyes_create(pg->root);
    lv_obj_align(pg->eyes, LV_ALIGN_CENTER, 0, -50);
    pg->message = owl_ui_label(pg->root, &owl_font_28, OWL_COLOR_CREAM, 390);
    lv_obj_align(pg->message, LV_ALIGN_CENTER, 0, 96);
    pg->hint = owl_ui_label(pg->root, &owl_font_20, OWL_COLOR_MUTED, 320);
    lv_obj_align(pg->hint, LV_ALIGN_CENTER, 0, 136);
}

/* What the owl shows when there is no track to display. */
static owl_mood_t idle_state(const owl_app_t *app, const owl_player_t *p, const char **message, const char **hint,
                             int32_t *gaze_x)
{
    *gaze_x = 0;
    if (app->link == OWL_LINK_NONE) {
        *message = "Offline";
        *hint = app->hid_paired ? "Media keys still work" : "Looking for Wi-Fi";
        return OWL_MOOD_SLEEPY;
    }
    if (app->link == OWL_LINK_BLE) {
        *message = "Bluetooth remote";
        *hint = "Play, skip and volume";
        return OWL_MOOD_AWAKE;
    }
    if (p->status == OWL_PLAYER_NO_DEVICE || p->status == OWL_PLAYER_UNKNOWN) {
        *message = "Open Spotify on your phone";
        *hint = "Tap to pick a device";
        *gaze_x = -70;
        return OWL_MOOD_SCANNING;
    }
    if (p->track.kind == OWL_ITEM_AD) {
        *message = "Ad break";
        *hint = "Back soon";
        return OWL_MOOD_DROWSY;
    }
    *message = "Nothing playing";
    *hint = "Swipe up for your library";
    return OWL_MOOD_DROWSY;
}

void owl_np_render(owl_np_page_t *pg, const owl_app_t *app, const owl_player_t *p, const owl_ui_inputs_t *in,
                   int64_t now_ms)
{
    char status[64];
    snprintf(status, sizeof status, "%s%s%s%s", p->status == OWL_PLAYER_PAUSED ? LV_SYMBOL_PAUSE "  " : "",
             in->wifi ? LV_SYMBOL_WIFI "  " : "", in->ble ? LV_SYMBOL_BLUETOOTH "  " : "",
             owl_ui_battery_symbol(in->battery_percent, in->charging));
    owl_ui_set_text(pg->status, status);

    bool show_track = app->link == OWL_LINK_API && p->has_track && p->status != OWL_PLAYER_NO_DEVICE;
    owl_ui_show(pg->title, show_track);
    owl_ui_show(pg->subtitle, show_track);
    owl_ui_show(pg->brand, show_track);
    owl_ui_show(pg->eyes, !show_track);
    owl_ui_show(pg->message, !show_track);
    owl_ui_show(pg->hint, !show_track);

    if (!show_track) {
        const char *message, *hint;
        int32_t gaze_x;
        owl_mood_t mood = idle_state(app, p, &message, &hint, &gaze_x);
        owl_eyes_set(pg->eyes, mood, gaze_x, 0);
        owl_ui_set_text(pg->message, message);
        owl_ui_set_text(pg->hint, hint);
        owl_ui_show(pg->art, false);
        owl_ui_show(pg->art_placeholder, false);
        owl_ui_show(pg->progress, false);
        owl_ui_show(pg->volume, false);
        owl_ui_show(pg->liked, false);
        return;
    }

    if (in->art != NULL && lv_image_get_src(pg->art) != in->art) {
        lv_image_set_src(pg->art, in->art);
    }
    owl_ui_show(pg->art, in->art != NULL);
    owl_ui_show(pg->art_placeholder, in->art == NULL);
    owl_ui_set_text(pg->title, p->track.title);
    owl_ui_show(pg->liked, p->liked);
    if (p->liked) {
        /* Sit just left of the title text, which is centred and may be shorter than the label. */
        lv_point_t size;
        lv_text_get_size(&size, p->track.title, &owl_font_28, 0, 0, LV_COORD_MAX, LV_TEXT_FLAG_EXPAND);
        int32_t x = -(LV_MIN(size.x, 320) / 2) - 16;
        if (lv_obj_get_x_aligned(pg->liked) != x) {
            lv_obj_align(pg->liked, LV_ALIGN_CENTER, x, 84);
        }
    }

    bool volume_overlay = now_ms < app->volume_overlay_until_ms && p->device.volume_percent >= 0;
    owl_ui_show(pg->volume, volume_overlay);
    owl_ui_show(pg->progress, !volume_overlay);
    if (volume_overlay) {
        char line[24];
        snprintf(line, sizeof line, "Volume %d%%", p->device.volume_percent);
        owl_ui_set_text(pg->subtitle, line);
        lv_arc_set_value(pg->volume, p->device.volume_percent);
    } else {
        owl_ui_set_text(pg->subtitle, p->track.subtitle);
    }

    uint32_t duration = p->track.duration_ms;
    uint64_t position = owl_player_progress_now(p, now_ms);
    int32_t permille = duration > 0 ? (int32_t)(position * 1000u / duration) : 0;
    lv_arc_set_value(pg->progress, permille);
    owl_ui_set_arc_color(pg->progress, p->status == OWL_PLAYER_PLAYING ? OWL_COLOR_CREAM : OWL_COLOR_MUTED);
}
