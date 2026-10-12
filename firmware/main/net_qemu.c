/* QEMU board: Ethernet through the OpenCores MAC that QEMU emulates. Saved Wi-Fi networks are only
 * stored here; the real boards join them (net_wifi.c). */
#include <string.h>

#include "esp_eth.h"
#include "esp_eth_mac_openeth.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "freertos/FreeRTOS.h"
#include "net.h"

static const char *TAG = "net";
static net_change_fn s_on_change;
static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static char s_ip[16]; /* under s_lock; "" while down */

static void on_ip_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    (void)arg;
    (void)base;
    if (id == IP_EVENT_ETH_GOT_IP) {
        const ip_event_got_ip_t *event = data;
        char ip[16];
        esp_ip4addr_ntoa(&event->ip_info.ip, ip, sizeof ip);
        ESP_LOGI(TAG, "network up, address %s", ip);
        portENTER_CRITICAL(&s_lock);
        memcpy(s_ip, ip, sizeof s_ip);
        portEXIT_CRITICAL(&s_lock);
        s_on_change(true, ip);
    } else if (id == IP_EVENT_ETH_LOST_IP) {
        ESP_LOGW(TAG, "network down");
        portENTER_CRITICAL(&s_lock);
        s_ip[0] = '\0';
        portEXIT_CRITICAL(&s_lock);
        s_on_change(false, NULL);
    }
}

void net_start(net_change_fn on_change, net_failed_fn on_failed)
{
    (void)on_failed; /* Ethernet has nothing to join */
    s_on_change = on_change;
    esp_netif_config_t netif_config = ESP_NETIF_DEFAULT_ETH();
    esp_netif_t *netif = esp_netif_new(&netif_config);
    eth_mac_config_t mac_config = ETH_MAC_DEFAULT_CONFIG();
    eth_phy_config_t phy_config = ETH_PHY_DEFAULT_CONFIG();
    phy_config.autonego_timeout_ms = 100; /* QEMU's PHY reports its link at once */
    esp_eth_mac_t *mac = esp_eth_mac_new_openeth(&mac_config);
    esp_eth_phy_t *phy = esp_eth_phy_new_generic(&phy_config);
    esp_eth_config_t eth_config = ETH_DEFAULT_CONFIG(mac, phy);
    esp_eth_handle_t eth = NULL;
    ESP_ERROR_CHECK(esp_eth_driver_install(&eth_config, &eth));
    ESP_ERROR_CHECK(esp_netif_attach(netif, esp_eth_new_netif_glue(eth)));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, ESP_EVENT_ANY_ID, on_ip_event, NULL));
    ESP_ERROR_CHECK(esp_eth_start(eth));
}

void net_networks_changed(const owl_settings_t *settings)
{
    ESP_LOGI(TAG, "%u Wi-Fi network(s) saved; the QEMU board stays on Ethernet",
             (unsigned)settings->n_networks);
}

void net_info(net_info_t *out)
{
    memset(out, 0, sizeof *out);
    portENTER_CRITICAL(&s_lock);
    memcpy(out->ip, s_ip, sizeof out->ip);
    portEXIT_CRITICAL(&s_lock);
    out->state = out->ip[0] != '\0' ? "ethernet" : "down";
}
