#include <string.h>

#include "owl_text.h"
#include "owl_ui_internal.h"

/* Row k shows the item at cursor + k - 2. Narrower rows further from the centre fit the circle. */
static const struct {
    int32_t y;
    int32_t width;
    const lv_font_t *font;
} ROWS[5] = {
    {-150, 230, &owl_font_20}, {-80, 300, &owl_font_20}, {-10, 340, &owl_font_28},
    {80, 300, &owl_font_20},   {150, 230, &owl_font_20},
};

void owl_list_ui_create(owl_list_ui_t *pg, lv_obj_t *parent)
{
    pg->root = owl_ui_page(parent);
    pg->position = owl_ui_ring(pg->root, 4, OWL_COLOR_BARK, OWL_COLOR_AMBER);
    lv_arc_set_rotation(pg->position, 0);
    lv_arc_set_bg_angles(pg->position, 320, 40);
    pg->heading = owl_ui_label(pg->root, &owl_font_14, OWL_COLOR_AMBER, 0);
    lv_obj_set_style_text_letter_space(pg->heading, 2, 0);
    lv_obj_align(pg->heading, LV_ALIGN_CENTER, 0, -196);
    for (int k = 0; k < 5; k++) {
        pg->rows[k] = owl_ui_label(pg->root, ROWS[k].font, OWL_COLOR_MUTED, ROWS[k].width);
        lv_obj_align(pg->rows[k], LV_ALIGN_CENTER, 0, ROWS[k].y);
    }
    pg->sub = owl_ui_label(pg->root, &owl_font_14, OWL_COLOR_MUTED, 300);
    lv_obj_align(pg->sub, LV_ALIGN_CENTER, 0, 24);
    pg->empty = owl_ui_label(pg->root, &owl_font_20, OWL_COLOR_MUTED, 300);
    lv_obj_align(pg->empty, LV_ALIGN_CENTER, 0, 0);
}

static const char *heading_for(const owl_nav_frame_t *f)
{
    if (f->screen == OWL_SCREEN_LIBRARY) {
        return "LIBRARY";
    }
    switch (f->list_kind) {
    case OWL_LIST_PLAYLISTS:
        return "PLAYLISTS";
    case OWL_LIST_SAVED_TRACKS:
        return "LIKED SONGS";
    case OWL_LIST_ALBUMS:
        return "ALBUMS";
    case OWL_LIST_RECENT:
        return "RECENTLY PLAYED";
    case OWL_LIST_DEVICES:
        return "DEVICES";
    case OWL_LIST_PLAYLIST_ITEMS:
        return "PLAYLIST";
    case OWL_LIST_ALBUM_TRACKS:
        return "ALBUM";
    case OWL_LIST_QUEUE:
        return "QUEUE";
    case OWL_LIST_NONE:
        break;
    }
    return "";
}

/* Text for one row; false when index is outside the list. */
static bool row_text(const owl_app_t *app, int index, char *title, size_t cap, const char **subtitle,
                     bool *disabled)
{
    const owl_nav_frame_t *f = owl_app_frame(app);
    *subtitle = "";
    *disabled = false;
    if (f->screen == OWL_SCREEN_LIBRARY) {
        if (index < 0 || index >= OWL_LIB_COUNT) {
            return false;
        }
        owl_utf8_copy(title, cap, owl_lib_entry_label((owl_lib_entry_t)index));
        return true;
    }
    const owl_list_page_t *list = app->list;
    if (list == NULL || index < 0 || index >= (int)list->count) {
        return false;
    }
    const owl_list_item_t *it = &list->items[index];
    owl_utf8_copy(title, cap, it->title);
    *subtitle = it->active ? "Playing now" : it->subtitle;
    *disabled = it->disabled;
    return true;
}

void owl_list_ui_render(owl_list_ui_t *pg, const owl_app_t *app)
{
    const owl_nav_frame_t *f = owl_app_frame(app);
    owl_ui_set_text(pg->heading, heading_for(f));

    bool loading = f->screen == OWL_SCREEN_BROWSE && app->list == NULL;
    int count = f->screen == OWL_SCREEN_LIBRARY ? OWL_LIB_COUNT : (app->list ? (int)app->list->count : 0);
    owl_ui_show(pg->empty, loading || count == 0);
    owl_ui_set_text(pg->empty, loading ? "Loading..." : "Nothing here yet");

    owl_ui_show(pg->position, count > 1);
    if (count > 1) {
        /* Filled up to the selected item, so the first item already shows a segment. */
        lv_arc_set_range(pg->position, 0, count);
        lv_arc_set_value(pg->position, f->cursor + 1);
    }

    owl_ui_show(pg->sub, false);
    for (int k = 0; k < 5; k++) {
        char title[OWL_NAME_LEN];
        const char *subtitle;
        bool disabled;
        bool present = !loading && row_text(app, f->cursor + k - 2, title, sizeof title, &subtitle, &disabled);
        owl_ui_show(pg->rows[k], present);
        if (!present) {
            continue;
        }
        owl_ui_set_text(pg->rows[k], title);
        lv_color_t color = OWL_COLOR_DIM;
        if (!disabled && k == 2) {
            color = OWL_COLOR_CREAM;
        } else if (!disabled && (k == 1 || k == 3)) {
            color = OWL_COLOR_MUTED;
        }
        owl_ui_set_text_color(pg->rows[k], color);
        if (k == 2 && subtitle[0] != '\0') {
            owl_ui_set_text(pg->sub, subtitle);
            owl_ui_show(pg->sub, true);
        }
    }
}
