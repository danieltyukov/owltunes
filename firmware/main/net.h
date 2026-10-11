#pragma once

#include <stdbool.h>

#include "owl_prov.h"

/* Runs on a network task when the owl gains (up, with its IPv4 address) or loses its network. */
typedef void (*net_change_fn)(bool up, const char *ip);

/* Start this board's network. esp_netif and the default event loop must be initialised. */
void net_start(net_change_fn on_change);

/* The saved Wi-Fi networks changed. */
void net_networks_changed(const owl_settings_t *settings);

typedef struct {
    const char *state; /* Wi-Fi: "idle", "joining", "online" or "waiting"; QEMU: "ethernet" or "down";
                        * "off" on a board without network support */
    char ssid[33];     /* the network being joined or used, "" when none */
    int rssi;          /* signal in dBm while online, else 0 */
    char ip[16];       /* "" when offline */
} net_info_t;

/* What the network is doing now. Any task. */
void net_info(net_info_t *out);
