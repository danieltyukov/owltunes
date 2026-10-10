#pragma once

#include <stdbool.h>

#include "owl_prov.h"

/* Runs on the event task when the owl gains (up, with its IPv4 address) or loses its network. */
typedef void (*net_change_fn)(bool up, const char *ip);

/* Start this board's network. esp_netif and the default event loop must be initialised. */
void net_start(net_change_fn on_change);

/* The saved Wi-Fi networks changed. */
void net_networks_changed(const owl_settings_t *settings);
