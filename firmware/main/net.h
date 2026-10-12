#pragma once

#include <stdbool.h>

#include "owl_prov.h"

/* Runs on a network task when the owl gains (up, with its IPv4 address) or loses its network. */
typedef void (*net_change_fn)(bool up, const char *ip);

/* Runs on a network task when joining a saved Wi-Fi network failed. error is one of the codes from
 * owl_wifi_fail_name(): "wifi_not_found", "wifi_wrong_password", "wifi_no_address", "wifi_failed". */
typedef void (*net_failed_fn)(const char *ssid, const char *error);

/* Start this board's network. esp_netif and the default event loop must be initialised. */
void net_start(net_change_fn on_change, net_failed_fn on_failed);

/* The saved Wi-Fi networks changed, or were loaded at boot. Safe to call before net_start. */
void net_networks_changed(const owl_settings_t *settings);

typedef struct {
    const char *state; /* Wi-Fi: "idle", "joining", "online" or "waiting"; QEMU: "ethernet" or "down" */
    char ssid[33];     /* the network being joined or used, "" when none */
    int rssi;          /* signal in dBm while online, else 0 */
    char ip[16];       /* "" when offline */
} net_info_t;

/* What the network is doing now. Any task. */
void net_info(net_info_t *out);
