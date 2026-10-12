/* Host stand-in for owl_ui.h (which needs LVGL): provisioning_task.h only uses the setup mode. */
#pragma once

typedef enum {
    OWL_UI_SETUP_OFF,
    OWL_UI_SETUP_WELCOME,
    OWL_UI_SETUP_LINK,
    OWL_UI_SETUP_LINKING,
    OWL_UI_SETUP_RELINK,
} owl_ui_setup_mode_t;
