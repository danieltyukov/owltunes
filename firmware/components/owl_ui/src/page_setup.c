#include <stdio.h>
#include <string.h>

#include "owl_ui_internal.h"

#define QR_SIZE 196

void owl_setup_ui_create(owl_setup_ui_t *pg, lv_obj_t *parent)
{
    pg->root = owl_ui_page(parent);
    pg->title = owl_ui_label(pg->root, &owl_font_28, OWL_COLOR_CREAM, 300);
    lv_obj_align(pg->title, LV_ALIGN_CENTER, 0, -162);
    /* Black modules on cream with a quiet zone: phone cameras read dark-on-light codes best. */
    pg->qr = lv_qrcode_create(pg->root);
    lv_qrcode_set_size(pg->qr, QR_SIZE);
    lv_qrcode_set_dark_color(pg->qr, OWL_COLOR_BG);
    lv_qrcode_set_light_color(pg->qr, OWL_COLOR_CREAM);
    lv_qrcode_set_quiet_zone(pg->qr, true);
    lv_obj_align(pg->qr, LV_ALIGN_CENTER, 0, -14);
    pg->eyes = owl_eyes_create(pg->root);
    lv_obj_align(pg->eyes, LV_ALIGN_CENTER, 0, -30);
    pg->name = owl_ui_label(pg->root, &owl_font_20, OWL_COLOR_CREAM, 300);
    lv_obj_align(pg->name, LV_ALIGN_CENTER, 0, 112);
    pg->hint = owl_ui_label(pg->root, &owl_font_14, OWL_COLOR_MUTED, 300);
    lv_obj_align(pg->hint, LV_ALIGN_CENTER, 0, 144);
    pg->error = owl_ui_label(pg->root, &owl_font_14, OWL_COLOR_AMBER, 260);
    lv_obj_align(pg->error, LV_ALIGN_CENTER, 0, 170);
    pg->qr_text[0] = '\0';
    pg->qr_ok = false;
}

/* Re-encode only when the address changes; an address that does not fit is not shown at all. */
static void update_qr(owl_setup_ui_t *pg, const char *url)
{
    if (strcmp(url, pg->qr_text) == 0) {
        return;
    }
    size_t len = strlen(url);
    pg->qr_ok =
        len > 0 && len < sizeof pg->qr_text && lv_qrcode_update(pg->qr, url, (uint32_t)len) == LV_RESULT_OK;
    snprintf(pg->qr_text, sizeof pg->qr_text, "%s", url);
}

void owl_setup_ui_render(owl_setup_ui_t *pg, const owl_ui_setup_t *setup)
{
    const char *title = "Hoot! Set me up";
    const char *hint = "Scan to set up Wi-Fi and Spotify";
    switch (setup->mode) {
    case OWL_UI_SETUP_LINK:
        title = "Link Spotify";
        hint = "Scan to log in with Spotify";
        break;
    case OWL_UI_SETUP_LINKING:
        title = "Linking Spotify";
        hint = "One moment";
        break;
    case OWL_UI_SETUP_RELINK:
        title = "Log in again";
        hint = "Spotify needs you to log in again";
        break;
    case OWL_UI_SETUP_OFF:
    case OWL_UI_SETUP_WELCOME:
        break;
    }
    bool linking = setup->mode == OWL_UI_SETUP_LINKING;
    update_qr(pg, setup->url != NULL ? setup->url : "");
    owl_ui_show(pg->qr, !linking && pg->qr_ok);
    owl_ui_show(pg->eyes, linking);
    if (linking) {
        owl_eyes_set(pg->eyes, OWL_MOOD_SCANNING, 0, 0);
    }
    owl_ui_set_text(pg->title, title);
    owl_ui_set_text(pg->name, setup->name);
    owl_ui_set_text(pg->hint, hint);
    owl_ui_set_text(pg->error, linking ? NULL : setup->error);
}
