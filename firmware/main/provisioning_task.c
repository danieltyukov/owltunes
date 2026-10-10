/* Owns the protocol state. Console lines and network changes arrive as messages on one queue,
 * so owl_prov_t is only ever touched by this task. */
#include "provisioning_task.h"

#include <stdlib.h>
#include <string.h>

#include "console.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "net.h"
#include "owl_prov.h"
#include "owl_text.h"
#include "settings_store.h"
#include "spotify_link.h"

#define VERIFY_RETRY_MS (5 * 60 * 1000)

static const char *TAG = "provisioning";

typedef enum { MSG_LINE, MSG_NETWORK } msg_kind_t;

typedef struct {
    msg_kind_t kind;
    bool up;
    char ip[16];
    char *text; /* MSG_LINE: the line, on the heap; the protocol task frees it */
} msg_t;

static owl_prov_t s_prov;
static QueueHandle_t s_queue;
static SemaphoreHandle_t s_view_lock;
static provisioning_view_t s_view;
static bool s_linking;
static bool s_relink;
static char s_error[64];
static bool s_save_pending; /* a save failed and must be retried */
static int64_t s_verify_at_ms = -1; /* when to check the saved login with Spotify; -1: not due */
static char s_out[OWL_PROV_LINE_MAX + 64];

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

/* esp_fill_random is a true RNG only while Wi-Fi or Bluetooth runs, as it does on the dev kits
 * during setup (P3). QEMU builds are test-only and get weaker randomness from the host; real
 * logins on P3 hardware run with the radio on. */
static void hw_random(uint8_t *buf, size_t len)
{
    esp_fill_random(buf, len);
}

static void emit(const char *event, const char *state, const char *key, const char *value)
{
    if (owl_prov_event(s_out, sizeof s_out, event, state, key, value)) {
        owl_console_write(s_out);
    }
}

static const char *sentence_for(spotify_token_result_t result)
{
    switch (result) {
    case SPOTIFY_TOKEN_BAD_CLIENT:
        return "Spotify rejected the client ID";
    case SPOTIFY_TOKEN_LOG_IN_AGAIN:
        return "Spotify refused the login, try again";
    case SPOTIFY_TOKEN_RETRY:
        return "Could not reach Spotify, try again";
    case SPOTIFY_TOKEN_BAD_RESPONSE:
        return "Spotify sent an unexpected answer";
    case SPOTIFY_TOKEN_OK:
        break;
    }
    return "";
}

static void publish_view(void)
{
    owl_ui_setup_mode_t mode = OWL_UI_SETUP_OFF;
    if (s_linking) {
        mode = OWL_UI_SETUP_LINKING;
    } else if (owl_prov_setup_state(&s_prov) == OWL_SETUP_STATE_NEEDS_WIFI) {
        mode = OWL_UI_SETUP_WELCOME;
    } else if (owl_prov_setup_state(&s_prov) == OWL_SETUP_STATE_NEEDS_SPOTIFY) {
        mode = s_relink ? OWL_UI_SETUP_RELINK : OWL_UI_SETUP_LINK;
    }
    xSemaphoreTake(s_view_lock, portMAX_DELAY);
    s_view.mode = mode;
    s_view.network_up = s_prov.network_up;
    owl_utf8_copy(s_view.error, sizeof s_view.error, s_error);
    xSemaphoreGive(s_view_lock);
}

/* Write the settings to flash. A failure keeps the save pending, so the next pass retries it. */
static bool persist(void)
{
    esp_err_t err = settings_store_save(&s_prov.settings);
    s_save_pending = err != ESP_OK;
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "saving settings failed: %s", esp_err_to_name(err));
    }
    return err == ESP_OK;
}

/* A new or rotated token must be on flash before the owl reports it linked or uses it. */
static bool persist_login(void)
{
    uint32_t actions = owl_prov_take_actions(&s_prov);
    if ((actions & OWL_PROV_DO_SAVE) != 0 || s_save_pending) {
        if (!persist()) {
            emit("spotify", "failed", "error", "storage");
            return false;
        }
    }
    return true;
}

static void exchange_code(void)
{
    static spotify_token_t token;
    char error[48];
    s_linking = true;
    s_error[0] = '\0';
    publish_view();
    emit("spotify", "linking", NULL, NULL);
    memset(&token, 0, sizeof token);
    spotify_token_result_t result = spotify_link_exchange(&s_prov.settings, s_prov.code, s_prov.session.verifier,
                                                          now_ms(), &token, error, sizeof error);
    bool ok = result == SPOTIFY_TOKEN_OK && token.refresh_token[0] != '\0';
    if (result == SPOTIFY_TOKEN_OK && !ok) {
        owl_utf8_copy(error, sizeof error, "no_refresh_token");
        result = SPOTIFY_TOKEN_BAD_RESPONSE;
    }
    owl_prov_finish_exchange(&s_prov, ok, token.refresh_token);
    memset(&token, 0, sizeof token);
    s_linking = false;
    if (ok) {
        s_relink = false;
        if (persist_login()) {
            emit("spotify", "linked", NULL, NULL);
        }
    } else {
        owl_utf8_copy(s_error, sizeof s_error, sentence_for(result));
        emit("spotify", "failed", "error", error);
    }
}

static void verify_saved_login(void)
{
    static spotify_token_t token;
    char error[48];
    memset(&token, 0, sizeof token);
    owl_utf8_copy(token.refresh_token, sizeof token.refresh_token, s_prov.settings.refresh_token);
    spotify_token_result_t result = spotify_link_refresh(&s_prov.settings, now_ms(), &token, error, sizeof error);
    bool dropped = owl_prov_apply_refresh(&s_prov, result, token.refresh_token);
    memset(&token, 0, sizeof token);
    if (result == SPOTIFY_TOKEN_OK) {
        s_verify_at_ms = -1;
        if (persist_login()) {
            emit("spotify", "linked", NULL, NULL);
        }
    } else if (dropped) {
        s_verify_at_ms = -1;
        s_relink = result == SPOTIFY_TOKEN_LOG_IN_AGAIN;
        owl_utf8_copy(s_error, sizeof s_error, s_relink ? "" : sentence_for(result));
        emit("spotify", "logged_out", "error", error);
    } else {
        s_verify_at_ms = now_ms() + VERIFY_RETRY_MS;
        ESP_LOGW(TAG, "could not check the saved login (%s); trying again later", error);
    }
}

/* Carry out what the protocol asked for, and the boot check of a saved login. */
static void do_work(void)
{
    uint32_t actions = owl_prov_take_actions(&s_prov);
    if (actions & OWL_PROV_DO_JOIN_WIFI) {
        net_networks_changed(&s_prov.settings);
    }
    if (actions & OWL_PROV_DO_EXCHANGE) {
        exchange_code();
        actions |= owl_prov_take_actions(&s_prov);
    }
    if (s_verify_at_ms >= 0 && s_prov.network_up && now_ms() >= s_verify_at_ms &&
        owl_prov_setup_state(&s_prov) == OWL_SETUP_STATE_READY) {
        verify_saved_login();
        actions |= owl_prov_take_actions(&s_prov);
    }
    if ((actions & OWL_PROV_DO_SAVE) != 0 || s_save_pending) {
        persist();
    }
}

static void handle(msg_t *msg)
{
    switch (msg->kind) {
    case MSG_LINE: {
        int64_t before = s_prov.session_expires_ms;
        if (owl_prov_handle_line(&s_prov, msg->text, now_ms(), s_out, sizeof s_out)) {
            owl_console_write(s_out);
        }
        if (s_prov.session_expires_ms != 0 && s_prov.session_expires_ms != before) {
            s_error[0] = '\0'; /* a new login started: the old failure no longer applies */
        }
        break;
    }
    case MSG_NETWORK:
        owl_prov_set_network(&s_prov, msg->up, msg->ip);
        emit("network", msg->up ? "up" : "down", "ip", msg->up ? msg->ip : NULL);
        break;
    }
    free(msg->text);
}

static void protocol_task(void *arg)
{
    (void)arg;
    msg_t msg;
    while (true) {
        if (xQueueReceive(s_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE) {
            handle(&msg);
        }
        do_work();
        publish_view();
    }
}

static void post_line(const char *line)
{
    msg_t msg = {.kind = MSG_LINE, .text = strdup(line)};
    if (msg.text == NULL || xQueueSend(s_queue, &msg, pdMS_TO_TICKS(1000)) != pdTRUE) {
        free(msg.text);
        ESP_LOGW(TAG, "dropped a console line");
    }
}

void provisioning_network(bool up, const char *ip)
{
    msg_t msg = {.kind = MSG_NETWORK, .up = up};
    owl_utf8_copy(msg.ip, sizeof msg.ip, ip);
    if (xQueueSend(s_queue, &msg, pdMS_TO_TICKS(100)) != pdTRUE) {
        ESP_LOGW(TAG, "dropped a network change");
    }
}

void provisioning_view(provisioning_view_t *out)
{
    xSemaphoreTake(s_view_lock, portMAX_DELAY);
    *out = s_view;
    xSemaphoreGive(s_view_lock);
}

void provisioning_start(const char *name, const char *fw)
{
    static owl_settings_t saved;
    bool have = settings_store_load(&saved);
    owl_prov_init(&s_prov, have ? &saved : NULL, name, fw, hw_random);
    memset(&saved, 0, sizeof saved);
    if (owl_prov_setup_state(&s_prov) == OWL_SETUP_STATE_READY) {
        s_verify_at_ms = 0; /* check the saved login once the network is up */
    }
    s_queue = xQueueCreate(8, sizeof(msg_t));
    s_view_lock = xSemaphoreCreateMutex();
    publish_view();
    xTaskCreate(protocol_task, "provisioning", 10240, NULL, 4, NULL);
    owl_console_start(post_line);
    ESP_LOGI(TAG, "%s %s, setup state %s", name, fw, owl_prov_setup_state_name(owl_prov_setup_state(&s_prov)));
}
