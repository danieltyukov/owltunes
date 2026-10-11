#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "owl_ui.h"

typedef struct {
    owl_ui_setup_mode_t mode;
    bool network_up;
    bool linked;        /* a Spotify login is saved */
    uint8_t n_networks; /* saved Wi-Fi networks */
    char error[64];     /* sentence for the setup screen, "" when there is none */
} provisioning_view_t;

/* Load the saved settings, take over the console and start the protocol task. */
void provisioning_start(const char *name, const char *fw);
/* A network change from the board's network code (any task). */
void provisioning_network(bool up, const char *ip);
/* What the setup screen shows now (any task). */
void provisioning_view(provisioning_view_t *out);
