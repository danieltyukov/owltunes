#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "lvgl.h"
#include "owl_app.h"
#include "owl_model.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The owl's round panel is 466 x 466 pixels. */
#define OWL_UI_RES 466

typedef enum {
    OWL_UI_SETUP_OFF,     /* normal use: the setup page stays hidden */
    OWL_UI_SETUP_WELCOME, /* first boot, no network yet */
    OWL_UI_SETUP_LINK,    /* online, waiting for the Spotify login */
    OWL_UI_SETUP_LINKING, /* exchanging the login code with Spotify */
    OWL_UI_SETUP_RELINK,  /* Spotify stopped accepting the saved login */
} owl_ui_setup_mode_t;

typedef struct {
    owl_ui_setup_mode_t mode;
    const char *url;   /* QR payload: the setup page address */
    const char *name;  /* the owl's name, so the person picks the right device */
    const char *error; /* a short sentence about the last failure, or NULL */
} owl_ui_setup_t;

typedef struct {
    const lv_image_dsc_t *art; /* decoded art for the current track, NULL until it is loaded */
    uint8_t battery_percent;
    bool charging;
    bool wifi;
    bool ble;
    owl_ui_setup_t setup; /* mode OWL_UI_SETUP_OFF unless the owl is being set up */
} owl_ui_inputs_t;

typedef struct owl_ui owl_ui_t;

/* Build every page on the display's active screen. There is one instance. */
owl_ui_t *owl_ui_create(lv_display_t *disp);

/* Bring the widgets in line with the state. Cheap when nothing changed; call after every state
 * change and a few times per second so the progress ring moves. */
void owl_ui_render(owl_ui_t *ui, const owl_app_t *app, const owl_player_t *player, const owl_ui_inputs_t *in,
                   int64_t now_ms);

#ifdef __cplusplus
}
#endif
