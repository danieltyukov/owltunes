#include <stdio.h>

#include "owl_ui_internal.h"

#define SLOT_SIZE 68
#define SLOT_RADIUS 168

void owl_presets_ui_create(owl_presets_ui_t *pg, lv_obj_t *parent)
{
    pg->root = owl_ui_page(parent);
    for (int i = 0; i < OWL_PRESET_COUNT; i++) {
        /* Slot 1 at the top, then clockwise every 45 degrees (LVGL angles grow clockwise from 3 o'clock). */
        int16_t angle = (int16_t)((270 + i * 45) % 360);
        int32_t x = (SLOT_RADIUS * lv_trigo_cos(angle)) >> LV_TRIGO_SHIFT;
        int32_t y = (SLOT_RADIUS * lv_trigo_sin(angle)) >> LV_TRIGO_SHIFT;
        lv_obj_t *slot = owl_ui_box(pg->root, SLOT_SIZE, SLOT_SIZE, OWL_COLOR_BG, LV_RADIUS_CIRCLE);
        lv_obj_set_style_border_width(slot, 3, 0);
        lv_obj_set_style_border_color(slot, OWL_COLOR_DIM, 0);
        lv_obj_align(slot, LV_ALIGN_CENTER, x, y);
        lv_obj_t *label = owl_ui_label(slot, &owl_font_20, OWL_COLOR_MUTED, 0);
        char number[4];
        snprintf(number, sizeof number, "%d", i + 1);
        lv_label_set_text(label, number);
        lv_obj_center(label);
        pg->slot[i] = slot;
        pg->slot_label[i] = label;
    }
    pg->name = owl_ui_label(pg->root, &owl_font_28, OWL_COLOR_CREAM, 240);
    lv_obj_align(pg->name, LV_ALIGN_CENTER, 0, -14);
    pg->hint = owl_ui_label(pg->root, &owl_font_14, OWL_COLOR_MUTED, 220);
    lv_obj_align(pg->hint, LV_ALIGN_CENTER, 0, 24);
}

static void style_slot(owl_presets_ui_t *pg, int i, bool selected, bool assigned)
{
    lv_color_t fill = selected ? OWL_COLOR_AMBER : (assigned ? OWL_COLOR_BARK : OWL_COLOR_BG);
    lv_color_t border = selected || assigned ? OWL_COLOR_AMBER : OWL_COLOR_DIM;
    lv_color_t text = selected ? OWL_COLOR_BG : (assigned ? OWL_COLOR_CREAM : OWL_COLOR_MUTED);
    if (!lv_color_eq(lv_obj_get_style_bg_color(pg->slot[i], LV_PART_MAIN), fill)) {
        lv_obj_set_style_bg_color(pg->slot[i], fill, 0);
    }
    if (!lv_color_eq(lv_obj_get_style_border_color(pg->slot[i], LV_PART_MAIN), border)) {
        lv_obj_set_style_border_color(pg->slot[i], border, 0);
    }
    owl_ui_set_text_color(pg->slot_label[i], text);
}

void owl_presets_ui_render(owl_presets_ui_t *pg, const owl_app_t *app)
{
    for (int i = 0; i < OWL_PRESET_COUNT; i++) {
        style_slot(pg, i, i == app->preset_cursor, app->presets[i].assigned);
    }
    const owl_preset_t *selected = &app->presets[app->preset_cursor];
    char empty[24];
    snprintf(empty, sizeof empty, "Empty slot %d", app->preset_cursor + 1);
    owl_ui_set_text(pg->name, selected->assigned ? selected->label : empty);
    const char *hint;
    if (app->wheel_open) {
        hint = "Release to play";
    } else if (selected->assigned) {
        hint = "Tap to play, hold to replace";
    } else {
        hint = "Hold to save what is playing";
    }
    owl_ui_set_text(pg->hint, hint);
}
