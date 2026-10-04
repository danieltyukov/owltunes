#include "owl_ui_internal.h"

struct owl_ui {
    lv_obj_t *screen;
    owl_np_page_t now_playing;
    owl_list_ui_t list;
    owl_presets_ui_t presets;
};

static owl_ui_t s_ui;

owl_ui_t *owl_ui_create(lv_display_t *disp)
{
    owl_ui_t *ui = &s_ui;
    ui->screen = lv_display_get_screen_active(disp);
    lv_obj_set_style_bg_color(ui->screen, OWL_COLOR_BG, 0);
    lv_obj_set_style_bg_opa(ui->screen, LV_OPA_COVER, 0);
    lv_obj_set_scrollable(ui->screen, false);
    owl_np_create(&ui->now_playing, ui->screen);
    owl_list_ui_create(&ui->list, ui->screen);
    owl_presets_ui_create(&ui->presets, ui->screen);
    return ui;
}

void owl_ui_render(owl_ui_t *ui, const owl_app_t *app, const owl_player_t *player, const owl_ui_inputs_t *in,
                   int64_t now_ms)
{
    owl_screen_t screen = owl_app_frame(app)->screen;
    bool list = screen == OWL_SCREEN_LIBRARY || screen == OWL_SCREEN_BROWSE;
    owl_ui_show(ui->now_playing.root, screen == OWL_SCREEN_NOW_PLAYING);
    owl_ui_show(ui->list.root, list);
    owl_ui_show(ui->presets.root, screen == OWL_SCREEN_PRESETS);
    if (screen == OWL_SCREEN_NOW_PLAYING) {
        owl_np_render(&ui->now_playing, app, player, in, now_ms);
    } else if (list) {
        owl_list_ui_render(&ui->list, app);
    } else if (screen == OWL_SCREEN_PRESETS) {
        owl_presets_ui_render(&ui->presets, app);
    }
}
