#include <string.h>

#include "owl_ui_internal.h"

lv_obj_t *owl_ui_page(lv_obj_t *parent)
{
    lv_obj_t *page = lv_obj_create(parent);
    lv_obj_remove_style_all(page);
    lv_obj_set_size(page, OWL_UI_RES, OWL_UI_RES);
    lv_obj_center(page);
    lv_obj_set_scrollable(page, false);
    lv_obj_set_clickable(page, false);
    return page;
}

lv_obj_t *owl_ui_box(lv_obj_t *parent, int32_t w, int32_t h, lv_color_t color, int32_t radius)
{
    lv_obj_t *box = lv_obj_create(parent);
    lv_obj_remove_style_all(box);
    lv_obj_set_size(box, w, h);
    lv_obj_set_style_bg_color(box, color, 0);
    lv_obj_set_style_bg_opa(box, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(box, radius, 0);
    lv_obj_set_scrollable(box, false);
    lv_obj_set_clickable(box, false);
    return box;
}

lv_obj_t *owl_ui_label(lv_obj_t *parent, const lv_font_t *font, lv_color_t color, int32_t width)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, color, 0);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    if (width > 0) {
        lv_obj_set_width(label, width);
        lv_obj_set_height(label, lv_font_get_line_height(font));
        lv_label_set_long_mode(label, LV_LABEL_LONG_MODE_DOTS);
    }
    lv_label_set_text(label, "");
    return label;
}

void owl_ui_set_text(lv_obj_t *label, const char *text)
{
    const char *want = text ? text : "";
    const char *have = lv_label_get_text(label);
    if (have == NULL || strcmp(have, want) != 0) {
        lv_label_set_text(label, want);
    }
}

void owl_ui_set_text_color(lv_obj_t *obj, lv_color_t color)
{
    if (!lv_color_eq(lv_obj_get_style_text_color(obj, LV_PART_MAIN), color)) {
        lv_obj_set_style_text_color(obj, color, 0);
    }
}

void owl_ui_set_arc_color(lv_obj_t *arc, lv_color_t color)
{
    if (!lv_color_eq(lv_obj_get_style_arc_color(arc, LV_PART_INDICATOR), color)) {
        lv_obj_set_style_arc_color(arc, color, LV_PART_INDICATOR);
    }
}

void owl_ui_show(lv_obj_t *obj, bool visible)
{
    if (lv_obj_is_hidden(obj) == visible) {
        lv_obj_set_hidden(obj, !visible);
    }
}

const char *owl_ui_battery_symbol(uint8_t percent, bool charging)
{
    if (charging) {
        return LV_SYMBOL_CHARGE;
    }
    if (percent >= 90) {
        return LV_SYMBOL_BATTERY_FULL;
    }
    if (percent >= 60) {
        return LV_SYMBOL_BATTERY_3;
    }
    if (percent >= 35) {
        return LV_SYMBOL_BATTERY_2;
    }
    if (percent >= 10) {
        return LV_SYMBOL_BATTERY_1;
    }
    return LV_SYMBOL_BATTERY_EMPTY;
}

lv_obj_t *owl_ui_ring(lv_obj_t *parent, int32_t width, lv_color_t track, lv_color_t fill)
{
    lv_obj_t *arc = lv_arc_create(parent);
    lv_obj_set_size(arc, OWL_UI_RES - 14, OWL_UI_RES - 14);
    lv_obj_center(arc);
    lv_arc_set_rotation(arc, 270);
    lv_arc_set_bg_angles(arc, 0, 360);
    lv_arc_set_range(arc, 0, 1000);
    lv_arc_set_value(arc, 0);
    lv_obj_remove_style(arc, NULL, LV_PART_KNOB);
    lv_obj_set_clickable(arc, false);
    lv_obj_set_style_arc_width(arc, width, LV_PART_MAIN);
    lv_obj_set_style_arc_width(arc, width, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(arc, track, LV_PART_MAIN);
    lv_obj_set_style_arc_color(arc, fill, LV_PART_INDICATOR);
    lv_obj_set_style_arc_rounded(arc, true, LV_PART_INDICATOR);
    return arc;
}
