/* Wi-Fi station mode on the real boards: join the saved networks in the order they were saved
 * (home first, then the phone hotspot), rejoin with backoff, and report every change to
 * provisioning. The decisions come from owl_wifi.h; one task carries them out. */
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "net.h"
#include "owl_wifi.h"

/* owl_wifi.h mirrors these so the host tests can use them; fail the build if ESP-IDF renumbers. */
_Static_assert(OWL_WIFI_REASON_AUTH_EXPIRE == WIFI_REASON_AUTH_EXPIRE, "reason code");
_Static_assert(OWL_WIFI_REASON_ASSOC_LEAVE == WIFI_REASON_ASSOC_LEAVE, "reason code");
_Static_assert(OWL_WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT == WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT, "reason code");
_Static_assert(OWL_WIFI_REASON_STA_LEAVING == WIFI_REASON_STA_LEAVING, "reason code");
_Static_assert(OWL_WIFI_REASON_NO_AP_FOUND == WIFI_REASON_NO_AP_FOUND, "reason code");
_Static_assert(OWL_WIFI_REASON_AUTH_FAIL == WIFI_REASON_AUTH_FAIL, "reason code");
_Static_assert(OWL_WIFI_REASON_HANDSHAKE_TIMEOUT == WIFI_REASON_HANDSHAKE_TIMEOUT, "reason code");
_Static_assert(OWL_WIFI_REASON_NO_AP_FOUND_W_COMPATIBLE_SECURITY ==
                   WIFI_REASON_NO_AP_FOUND_W_COMPATIBLE_SECURITY,
               "reason code");
_Static_assert(OWL_WIFI_REASON_NO_AP_FOUND_IN_AUTHMODE_THRESHOLD ==
                   WIFI_REASON_NO_AP_FOUND_IN_AUTHMODE_THRESHOLD,
               "reason code");
_Static_assert(OWL_WIFI_REASON_NO_AP_FOUND_IN_RSSI_THRESHOLD == WIFI_REASON_NO_AP_FOUND_IN_RSSI_THRESHOLD,
               "reason code");
_Static_assert(OWL_WIFI_MAX_NETWORKS == OWL_PROV_MAX_NETWORKS, "network list sizes");
/* A saved SSID (at most 32 bytes) or password (at most 64) fills the driver's field exactly. */
_Static_assert(sizeof(((wifi_config_t *)0)->sta.ssid) == OWL_SSID_LEN - 1, "SSID size");
_Static_assert(sizeof(((wifi_config_t *)0)->sta.password) == OWL_WIFI_PASSWORD_LEN - 1, "password size");
_Static_assert(sizeof(((net_info_t *)0)->ssid) == OWL_SSID_LEN, "SSID size");

#define LONGEST_WAIT_MS 1000 /* the join task looks at the saved list at least this often */

static const char *TAG = "net";

typedef enum { EV_WAKE, EV_DISCONNECTED, EV_GOT_IP } ev_kind_t;

typedef struct {
    ev_kind_t kind;
    int reason;  /* EV_DISCONNECTED */
    char ip[16]; /* EV_GOT_IP */
} ev_t;

static net_change_fn s_on_change;
static net_failed_fn s_on_failed;
static QueueHandle_t s_events;

/* Shared with other tasks under s_lock. net_networks_changed may run before net_start. */
static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static owl_wifi_network_t s_saved[OWL_PROV_MAX_NETWORKS]; /* what provisioning saved last */
static uint8_t s_n_saved;
static bool s_saved_changed; /* the join task has not taken s_saved yet */
static net_info_t s_info = {.state = "idle"};

/* Owned by the join task. */
static owl_wifi_t s_plan;
static owl_wifi_network_t s_networks[OWL_PROV_MAX_NETWORKS];
static char s_ip[16];       /* the address from the last IP_EVENT_STA_GOT_IP */
static char s_reported[16]; /* the address provisioning heard last, "" when it heard "down" */

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

static void wipe(void *p, size_t n)
{
    for (volatile unsigned char *b = p; n > 0; n--, b++) {
        *b = 0;
    }
}

static void post(const ev_t *ev, TickType_t wait)
{
    if (s_events != NULL && xQueueSend(s_events, ev, wait) != pdTRUE && ev->kind != EV_WAKE) {
        ESP_LOGW(TAG, "dropped a Wi-Fi event");
    }
}

/* With the queue full the join task is busy anyway and finds the new list on its next pass. */
static void wake(void)
{
    ev_t ev = {.kind = EV_WAKE};
    post(&ev, 0);
}

static void on_wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    (void)arg;
    (void)base;
    if (id == WIFI_EVENT_STA_DISCONNECTED) {
        const wifi_event_sta_disconnected_t *event = data;
        ev_t ev = {.kind = EV_DISCONNECTED, .reason = event->reason};
        post(&ev, pdMS_TO_TICKS(100));
    }
}

static void on_ip_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    (void)arg;
    (void)base;
    if (id == IP_EVENT_STA_GOT_IP) {
        const ip_event_got_ip_t *event = data;
        ev_t ev = {.kind = EV_GOT_IP};
        esp_ip4addr_ntoa(&event->ip_info.ip, ev.ip, sizeof ev.ip);
        post(&ev, pdMS_TO_TICKS(100));
    }
}

/* wifi_config_t has no room for a terminator after a 32-byte SSID or a 64-byte password (a hex
 * PSK), so both are copied by length rather than as C strings. */
static void connect_to(uint8_t index)
{
    const owl_wifi_network_t *n = &s_networks[index];
    wifi_config_t config;
    memset(&config, 0, sizeof config);
    memcpy(config.sta.ssid, n->ssid, strnlen(n->ssid, sizeof config.sta.ssid));
    memcpy(config.sta.password, n->password, strnlen(n->password, sizeof config.sta.password));
    /* WPA2 or better (WPA3 included) when there is a password; SAE in both modes covers phone
     * hotspots that default to WPA3. */
    config.sta.threshold.authmode = n->password[0] != '\0' ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    config.sta.sae_pwe_h2e = WPA3_SAE_PWE_BOTH;
    config.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
    config.sta.sort_method = WIFI_CONNECT_AP_BY_SIGNAL;
    ESP_LOGI(TAG, "joining \"%s\"", n->ssid);
    /* ESP-IDF refuses a new config mid-connect. The leave is reported as ASSOC_LEAVE or
     * STA_LEAVING (or not at all when the station was idle), and the plan ignores it. */
    esp_wifi_disconnect();
    esp_err_t err = esp_wifi_set_config(WIFI_IF_STA, &config);
    wipe(&config, sizeof config); /* it held the password */
    if (err == ESP_OK) {
        err = esp_wifi_connect();
    }
    if (err != ESP_OK) {
        /* No event will come; the attempt times out and the plan moves on. */
        ESP_LOGE(TAG, "could not start joining: %s", esp_err_to_name(err));
    }
}

static void carry_out(owl_wifi_step_t step)
{
    if (step.failed != OWL_WIFI_FAIL_NONE) {
        const char *ssid = s_networks[step.failed_index].ssid;
        const char *error = owl_wifi_fail_name(step.failed);
        ESP_LOGW(TAG, "could not join \"%s\": %s", ssid, error);
        s_on_failed(ssid, error);
    }
    if (step.action == OWL_WIFI_DO_CONNECT) {
        connect_to(step.index);
    } else if (step.action == OWL_WIFI_DO_STOP) {
        esp_wifi_disconnect();
    }
}

static bool saved_changed(void)
{
    portENTER_CRITICAL(&s_lock);
    bool changed = s_saved_changed;
    portEXIT_CRITICAL(&s_lock);
    return changed;
}

/* Take the list provisioning saved. A working connection stays when its network is still in the
 * list with the same password. */
static owl_wifi_step_t take_networks(void)
{
    bool online = s_plan.state == OWL_WIFI_ONLINE;
    const owl_wifi_network_t *joined = &s_networks[s_plan.index];
    int keep = -1;
    portENTER_CRITICAL(&s_lock);
    uint8_t n = s_n_saved;
    for (uint8_t i = 0; online && i < n; i++) {
        if (strcmp(s_saved[i].ssid, joined->ssid) == 0 &&
            strcmp(s_saved[i].password, joined->password) == 0) {
            keep = i;
        }
    }
    memcpy(s_networks, s_saved, sizeof s_networks);
    s_saved_changed = false;
    portEXIT_CRITICAL(&s_lock);
    ESP_LOGI(TAG, "%u network(s) saved", (unsigned)n);
    return owl_wifi_set_networks(&s_plan, n, keep, now_ms());
}

static void handle(const ev_t *ev)
{
    switch (ev->kind) {
    case EV_DISCONNECTED:
        ESP_LOGI(TAG, "disconnected (reason %d) while %s", ev->reason, owl_wifi_state_name(s_plan.state));
        carry_out(owl_wifi_disconnected(&s_plan, ev->reason, now_ms()));
        break;
    case EV_GOT_IP:
        memcpy(s_ip, ev->ip, sizeof s_ip);
        carry_out(owl_wifi_got_address(&s_plan));
        break;
    case EV_WAKE:
        break;
    }
}

/* Tell provisioning when the owl comes online, goes offline or gets a new address, and keep what
 * net_info reports up to date. */
static void publish(void)
{
    bool up = s_plan.state == OWL_WIFI_ONLINE;
    bool joined = up || s_plan.state == OWL_WIFI_JOINING;
    if (strcmp(up ? s_ip : "", s_reported) != 0) {
        memcpy(s_reported, up ? s_ip : "", up ? sizeof s_reported : 1);
        if (up) {
            ESP_LOGI(TAG, "online at %s", s_ip);
        } else {
            ESP_LOGW(TAG, "offline");
        }
        s_on_change(up, up ? s_ip : NULL);
    }
    portENTER_CRITICAL(&s_lock);
    s_info.state = owl_wifi_state_name(s_plan.state);
    memset(s_info.ssid, 0, sizeof s_info.ssid);
    memset(s_info.ip, 0, sizeof s_info.ip);
    if (joined) {
        memcpy(s_info.ssid, s_networks[s_plan.index].ssid, sizeof s_info.ssid);
    }
    if (up) {
        memcpy(s_info.ip, s_ip, sizeof s_info.ip);
    }
    portEXIT_CRITICAL(&s_lock);
}

static TickType_t ticks_until(int64_t deadline_ms)
{
    int64_t wait_ms = deadline_ms - now_ms();
    if (wait_ms < 0) {
        wait_ms = 0;
    }
    return pdMS_TO_TICKS(wait_ms < LONGEST_WAIT_MS ? wait_ms : LONGEST_WAIT_MS);
}

static void join_task(void *arg)
{
    (void)arg;
    while (true) {
        ev_t ev;
        if (xQueueReceive(s_events, &ev, ticks_until(owl_wifi_deadline(&s_plan))) == pdTRUE) {
            handle(&ev);
        }
        if (saved_changed()) {
            carry_out(take_networks());
        }
        carry_out(owl_wifi_tick(&s_plan, now_ms())); /* nothing unless a deadline has passed */
        publish();
    }
}

void net_start(net_change_fn on_change, net_failed_fn on_failed)
{
    s_on_change = on_change;
    s_on_failed = on_failed;
    owl_wifi_init(&s_plan);
    s_events = xQueueCreate(16, sizeof(ev_t));
    configASSERT(s_events != NULL);
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM)); /* provisioning keeps the networks */
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED, on_wifi_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_ip_event, NULL));
    /* The radio starts even with no network saved. That also makes esp_fill_random a true random
     * source for the PKCE verifier made during setup. */
    ESP_ERROR_CHECK(esp_wifi_start());
    portENTER_CRITICAL(&s_lock);
    s_saved_changed = true; /* whatever provisioning loaded at boot, even nothing */
    portEXIT_CRITICAL(&s_lock);
    BaseType_t created = xTaskCreatePinnedToCore(join_task, "wifi_join", 4096, NULL, 5, NULL, 0);
    configASSERT(created == pdPASS);
    wake();
}

void net_networks_changed(const owl_settings_t *settings)
{
    uint8_t n = settings->n_networks <= OWL_PROV_MAX_NETWORKS ? settings->n_networks : OWL_PROV_MAX_NETWORKS;
    portENTER_CRITICAL(&s_lock);
    memcpy(s_saved, settings->networks, sizeof s_saved);
    s_n_saved = n;
    s_saved_changed = true;
    portEXIT_CRITICAL(&s_lock);
    wake();
}

void net_info(net_info_t *out)
{
    portENTER_CRITICAL(&s_lock);
    *out = s_info;
    portEXIT_CRITICAL(&s_lock);
    wifi_ap_record_t ap;
    out->rssi = out->ip[0] != '\0' && esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
}
