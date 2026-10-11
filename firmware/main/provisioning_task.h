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

/* Load the saved settings, hand the saved Wi-Fi networks to the network code and start the
 * protocol task. */
void provisioning_start(const char *name, const char *fw);
/* One console line that starts with OWL_PROV_PREFIX (console task). */
void provisioning_line(const char *line);
/* A network change from the board's network code (any task). Only the newest state is kept: the
 * protocol task reports it once it gets to it. */
void provisioning_network(bool up, const char *ip);
/* Joining a saved Wi-Fi network failed (any task); the setup page hears about it. */
void provisioning_network_failed(const char *ssid, const char *error);
/* What the setup screen shows now (any task). */
void provisioning_view(provisioning_view_t *out);
