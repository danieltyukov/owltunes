/* Owns the protocol state and the Spotify login. Console lines, login codes, Wi-Fi failures and
 * access-token requests arrive as messages on one queue, and the newest network state is handed over
 * beside it, so owl_prov_t and the access token are only ever touched by this task. */
#include "provisioning_task.h"

#include <stdlib.h>
#include <string.h>

#include "api_gate.h"
#include "callback_server.h"
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

/* After a refresh answer the gate lets through (an unexpected reply), the next automatic refresh
 * waits this long. Rate limits, server errors and lost connections wait for the gate instead. */
#define REFRESH_RETRY_MS (5 * 60 * 1000)

static const char *TAG = "provisioning";

typedef enum { MSG_LINE, MSG_CODE, MSG_NETWORK, MSG_NETWORK_FAILED, MSG_TOKEN } msg_kind_t;

/* Overwrite a string that held a secret before it is freed. */
static void wipe(char *s)
{
    for (volatile char *p = s; p != NULL && *p != '\0'; p++) {
        *p = '\0';
    }
}

typedef struct {
    msg_kind_t kind;
    char *text;   /* MSG_LINE: the line; MSG_CODE: the code; MSG_NETWORK_FAILED: the SSID. On the heap;
                   * the protocol task frees both */
    char *state;  /* MSG_CODE: the state; MSG_NETWORK_FAILED: the error code */
    bool force;   /* MSG_TOKEN: refresh even when the token looks valid */
    uint32_t seq; /* MSG_TOKEN: repeated in the reply, so a late reply to an earlier request is skipped */
} msg_t;

typedef struct {
    uint32_t seq;
    provisioning_token_t result;
    int64_t expires_at_ms;
    char token[SPOTIFY_ACCESS_TOKEN_LEN];
} token_reply_t;

static owl_prov_t s_prov;
static QueueHandle_t s_queue;
static QueueHandle_t s_code_reply;  /* one slot: the verdict on the code the HTTP server waits for */
static QueueHandle_t s_token_reply; /* one slot: the answer to provisioning_access_token */
static SemaphoreHandle_t s_token_lock;
static SemaphoreHandle_t s_view_lock;
static provisioning_view_t s_view;
static bool s_linking;
static bool s_relink;
static char s_error[64];
static bool s_save_pending;             /* a save failed and must be retried */
static bool s_boot_check;               /* the saved login has not been refreshed since the start */
static spotify_token_t s_access;        /* the current access token; its refresh_token stays empty */
static int64_t s_refresh_not_before_ms; /* see REFRESH_RETRY_MS; 0: no wait */
static int64_t s_refreshed_at_ms;       /* the last successful refresh or login (OWL_PROV_REFRESH_MIN_MS) */
static uint32_t s_login_seq;
static char s_out[OWL_PROV_LINE_MAX + 64];

/* The newest network state. A burst of changes during a long HTTPS call must not be lost to a full
 * queue, so the network code writes it here and the task applies whatever is newest. */
static portMUX_TYPE s_net_lock = portMUX_INITIALIZER_UNLOCKED;
static bool s_net_up;
static char s_net_ip[16];
static bool s_net_dirty;

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

/* ESP-IDF documents esp_fill_random as giving true random numbers while Wi-Fi or Bluetooth is
 * enabled. The real boards enable Wi-Fi at boot, before the console (net_wifi.c, main.c), and
 * owl_prov refuses spotify_begin while the owl is offline, so the PKCE verifier is made while
 * Wi-Fi is enabled. That is the documented condition and no more: ESP-IDF adds that the radio's
 * entropy source may be idle while the radio sleeps (Wi-Fi modem sleep is on by default), and QEMU
 * builds (test-only) use the host's generator. bootloader_random_enable() is not used: ESP-IDF says
 * it must not run while the radio or the ADC is in use. */
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
    s_view.linked = s_prov.settings.refresh_token[0] != '\0';
    s_view.n_networks = s_prov.settings.n_networks;
    owl_utf8_copy(s_view.error, sizeof s_view.error, s_error);
    s_view.login_seq = s_login_seq;
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

static void keep_access(const spotify_token_t *token)
{
    owl_utf8_copy(s_access.access_token, sizeof s_access.access_token, token->access_token);
    s_access.expires_at_ms = token->expires_at_ms;
}

static void forget_access(void)
{
    memset(&s_access, 0, sizeof s_access);
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
    spotify_token_result_t result = spotify_link_exchange(
        &s_prov.settings, s_prov.code, s_prov.session.verifier, now_ms(), &token, error, sizeof error);
    bool ok = result == SPOTIFY_TOKEN_OK && token.refresh_token[0] != '\0';
    if (result == SPOTIFY_TOKEN_OK && !ok) {
        owl_utf8_copy(error, sizeof error, "no_refresh_token");
        result = SPOTIFY_TOKEN_BAD_RESPONSE;
    }
    owl_prov_finish_exchange(&s_prov, ok, token.refresh_token);
    if (ok) {
        keep_access(&token); /* handed out only once the login is on flash (token_verdict) */
    }
    memset(&token, 0, sizeof token);
    s_linking = false;
    if (ok) {
        s_relink = false;
        s_boot_check = false; /* this login is reported below */
        s_refresh_not_before_ms = 0;
        s_refreshed_at_ms = now_ms();
        s_login_seq++; /* the runtime drops a token from the login this one replaced */
        if (persist_login()) {
            emit("spotify", "linked", NULL, NULL);
        }
    } else {
        owl_utf8_copy(s_error, sizeof s_error, sentence_for(result));
        emit("spotify", "failed", "error", error);
    }
}

/* Refresh the saved login: keep the new access token, save a rotated refresh token before anything
 * uses it (spec 9.6), and forget a login Spotify refused. The first refresh since the start is the
 * check of the saved login and reports "linked" when it passes. True when a new token arrived. */
static bool refresh_login(void)
{
    static spotify_token_t token;
    char error[48];
    memset(&token, 0, sizeof token);
    owl_utf8_copy(token.refresh_token, sizeof token.refresh_token, s_prov.settings.refresh_token);
    spotify_token_result_t result =
        spotify_link_refresh(&s_prov.settings, now_ms(), &token, error, sizeof error);
    bool dropped = owl_prov_apply_refresh(&s_prov, result, token.refresh_token);
    if (result == SPOTIFY_TOKEN_OK) {
        keep_access(&token);
    }
    memset(&token, 0, sizeof token);
    if (result == SPOTIFY_TOKEN_OK) {
        bool boot_check = s_boot_check;
        int64_t now = now_ms();
        s_boot_check = false;
        s_refresh_not_before_ms = 0;
        s_refreshed_at_ms = now;
        if (s_access.expires_at_ms - now <= 2 * SPOTIFY_REFRESH_MARGIN_MS) {
            /* Spotify documents an hour; the next automatic refresh still waits OWL_PROV_REFRESH_MIN_MS. */
            ESP_LOGW(TAG, "the new access token lasts only %d s",
                     (int)((s_access.expires_at_ms - now) / 1000));
        }
        if (persist_login() && boot_check) {
            emit("spotify", "linked", NULL, NULL);
        }
        return true;
    }
    if (dropped) {
        forget_access();
        s_boot_check = false;
        s_relink = result == SPOTIFY_TOKEN_LOG_IN_AGAIN;
        owl_utf8_copy(s_error, sizeof s_error, s_relink ? "" : sentence_for(result));
        emit("spotify", "logged_out", "error", error);
        return false;
    }
    if (result != SPOTIFY_TOKEN_RETRY) {
        s_refresh_not_before_ms = now_ms() + REFRESH_RETRY_MS; /* the gate did not hold this back */
    }
    ESP_LOGW(TAG, "could not refresh the saved login (%s); trying again later", error);
    return false;
}

/* Whether to ask Spotify for a new access token now (owl_prov_refresh_due). */
static bool refresh_due(bool force)
{
    int64_t now = now_ms();
    owl_prov_refresh_t r = {
        .force = force,
        .gate_open = api_gate_open(now),
        .save_pending = s_save_pending,
        .not_before_ms = s_refresh_not_before_ms,
        .refreshed_at_ms = s_refreshed_at_ms,
    };
    return owl_prov_refresh_due(&s_prov, &s_access, &r, now);
}

/* What a token request gets. fresh: this request refreshed the token. */
static provisioning_token_t token_verdict(bool force, bool fresh)
{
    if (owl_prov_setup_state(&s_prov) != OWL_SETUP_STATE_READY) {
        return s_relink ? PROVISIONING_TOKEN_LOGGED_OUT : PROVISIONING_TOKEN_NOT_LINKED;
    }
    if (s_save_pending) {
        return PROVISIONING_TOKEN_STORAGE; /* spec 9.6: nothing is used before the login is on flash */
    }
    if ((force && !fresh) || spotify_token_needs_refresh(&s_access, now_ms())) {
        return PROVISIONING_TOKEN_RETRY;
    }
    return PROVISIONING_TOKEN_OK;
}

static void reply_token(bool force, uint32_t seq)
{
    static token_reply_t reply;
    memset(&reply, 0, sizeof reply);
    reply.seq = seq;
    bool fresh = refresh_due(force) && refresh_login();
    reply.result = token_verdict(force, fresh);
    if (force && !fresh) {
        /* Spotify refused this token: no later request gets it either, and the next automatic refresh
         * goes as soon as the gate allows instead of waiting for the floor. */
        forget_access();
        s_refreshed_at_ms = 0;
    }
    if (reply.result == PROVISIONING_TOKEN_OK) {
        reply.expires_at_ms = s_access.expires_at_ms;
        owl_utf8_copy(reply.token, sizeof reply.token, s_access.access_token);
    }
    xQueueOverwrite(s_token_reply, &reply);
    memset(&reply, 0, sizeof reply);
}

/* Carry out what the protocol asked for, and keep the access token fresh. */
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
    if ((actions & OWL_PROV_DO_SAVE) != 0 || s_save_pending) {
        persist();
    }
    /* A minute before the access token expires, and at the start (the check of the saved login).
     * After the save above: a rotated refresh token is not used again before it is on flash. */
    if (refresh_due(false)) {
        refresh_login();
        if ((owl_prov_take_actions(&s_prov) & OWL_PROV_DO_SAVE) != 0) {
            persist(); /* a login Spotify refused is forgotten on flash too */
        }
    }
    if (s_prov.settings.refresh_token[0] == '\0') {
        forget_access(); /* logged out, or a new client ID: the old token is no longer ours */
    }
}

static void apply_network(void)
{
    char ip[16];
    portENTER_CRITICAL(&s_net_lock);
    bool dirty = s_net_dirty;
    bool up = s_net_up;
    memcpy(ip, s_net_ip, sizeof ip);
    s_net_dirty = false;
    portEXIT_CRITICAL(&s_net_lock);
    if (dirty && (up != s_prov.network_up || strcmp(ip, s_prov.ip) != 0)) {
        owl_prov_set_network(&s_prov, up, ip);
        emit("network", up ? "up" : "down", "ip", up ? ip : NULL);
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
        wipe(msg->text); /* the line may hold a Wi-Fi password */
        break;
    }
    case MSG_CODE: {
        const char *error = owl_prov_accept_code(&s_prov, msg->text, msg->state, now_ms());
        xQueueOverwrite(s_code_reply, &error);
        wipe(msg->text); /* the login code */
        break;
    }
    case MSG_NETWORK:
        break; /* only a wake-up: apply_network picks up the newest state */
    case MSG_NETWORK_FAILED:
        if (owl_prov_network_failed(s_out, sizeof s_out, msg->text, msg->state)) {
            owl_console_write(s_out);
        }
        break;
    case MSG_TOKEN:
        reply_token(msg->force, msg->seq);
        break;
    }
    free(msg->text);
    free(msg->state);
}

/* Runs on the HTTP server task: hand the code to the protocol task and wait for its verdict. */
static const char *on_code(const char *code, const char *state)
{
    msg_t msg = {.kind = MSG_CODE, .text = strdup(code), .state = strdup(state)};
    const char *error = "busy";
    xQueueReset(s_code_reply);
    if (msg.text != NULL && msg.state != NULL && xQueueSend(s_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE) {
        if (xQueueReceive(s_code_reply, &error, pdMS_TO_TICKS(5000)) != pdTRUE) {
            error = "busy";
        }
    } else {
        free(msg.text);
        free(msg.state);
    }
    return error;
}

/* The LAN callback listens only while a login is open (spec 9.7: the authorisation window). */
static void update_callback_server(void)
{
    bool want = s_prov.network_up && s_prov.session_expires_ms != 0 && now_ms() < s_prov.session_expires_ms;
    if (want && !callback_server_running()) {
        esp_err_t err = callback_server_start(on_code);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "callback server failed to start: %s", esp_err_to_name(err));
        }
    } else if (!want && callback_server_running()) {
        callback_server_stop(); /* a failure is logged and the server kept: the next pass tries again */
    }
}

static void protocol_task(void *arg)
{
    (void)arg;
    msg_t msg;
    while (true) {
        if (xQueueReceive(s_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE) {
            apply_network(); /* a token request after a network change must see the change */
            handle(&msg);
        }
        apply_network();
        do_work();
        update_callback_server();
        publish_view();
    }
}

void provisioning_line(const char *line)
{
    msg_t msg = {.kind = MSG_LINE, .text = strdup(line)};
    if (msg.text == NULL || xQueueSend(s_queue, &msg, pdMS_TO_TICKS(1000)) != pdTRUE) {
        wipe(msg.text);
        free(msg.text);
        ESP_LOGW(TAG, "dropped a console line");
    }
}

void provisioning_network(bool up, const char *ip)
{
    portENTER_CRITICAL(&s_net_lock);
    s_net_up = up;
    owl_utf8_copy(s_net_ip, sizeof s_net_ip, up ? ip : NULL);
    s_net_dirty = true;
    portEXIT_CRITICAL(&s_net_lock);
    msg_t msg = {.kind = MSG_NETWORK};
    xQueueSend(s_queue, &msg, 0); /* only a wake-up: with the queue full the task runs soon anyway */
}

void provisioning_network_failed(const char *ssid, const char *error)
{
    msg_t msg = {.kind = MSG_NETWORK_FAILED, .text = strdup(ssid), .state = strdup(error)};
    if (msg.text == NULL || msg.state == NULL || xQueueSend(s_queue, &msg, pdMS_TO_TICKS(100)) != pdTRUE) {
        free(msg.text);
        free(msg.state);
        ESP_LOGW(TAG, "dropped a Wi-Fi failure report");
    }
}

void provisioning_view(provisioning_view_t *out)
{
    xSemaphoreTake(s_view_lock, portMAX_DELAY);
    *out = s_view;
    xSemaphoreGive(s_view_lock);
}

provisioning_token_t provisioning_access_token(char *out, size_t cap, int64_t *expires_at_ms,
                                               bool force_refresh, uint32_t timeout_ms)
{
    static token_reply_t reply; /* both guarded by s_token_lock */
    static uint32_t seq;
    static const token_reply_t blank;
    provisioning_token_t result = PROVISIONING_TOKEN_RETRY;
    out[0] = '\0';
    *expires_at_ms = 0;
    xSemaphoreTake(s_token_lock, portMAX_DELAY); /* one request in flight */
    msg_t msg = {.kind = MSG_TOKEN, .force = force_refresh, .seq = ++seq};
    bool answered = false;
    if (xQueueSend(s_queue, &msg, pdMS_TO_TICKS(timeout_ms)) == pdTRUE) {
        /* The reply to an earlier request that timed out may come first: skip it, within one deadline. */
        TickType_t limit = pdMS_TO_TICKS(timeout_ms);
        TickType_t start = xTaskGetTickCount();
        TickType_t spent = 0;
        while (!answered && spent < limit && xQueueReceive(s_token_reply, &reply, limit - spent) == pdTRUE) {
            answered = reply.seq == msg.seq;
            spent = xTaskGetTickCount() - start;
        }
    }
    if (answered) {
        result = reply.result;
        if (result == PROVISIONING_TOKEN_OK) {
            if (owl_utf8_copy(out, cap, reply.token) == strlen(reply.token)) {
                *expires_at_ms = reply.expires_at_ms;
            } else {
                memset(out, 0, cap); /* never hand out part of a token */
                result = PROVISIONING_TOKEN_RETRY;
            }
        }
    }
    memset(&reply, 0, sizeof reply);
    xQueueOverwrite(s_token_reply, &blank); /* the queue's own storage held the token too */
    xQueueReset(s_token_reply);
    xSemaphoreGive(s_token_lock);
    return result;
}

void provisioning_start(const char *name, const char *fw)
{
    static owl_settings_t saved;
    bool have = settings_store_load(&saved);
    owl_prov_init(&s_prov, have ? &saved : NULL, name, fw, hw_random);
    memset(&saved, 0, sizeof saved);
    /* The first refresh, once the network is up, checks the saved login (do_work). */
    s_boot_check = owl_prov_setup_state(&s_prov) == OWL_SETUP_STATE_READY;
    s_queue = xQueueCreate(8, sizeof(msg_t));
    s_code_reply = xQueueCreate(1, sizeof(const char *));
    s_token_reply = xQueueCreate(1, sizeof(token_reply_t));
    s_token_lock = xSemaphoreCreateMutex();
    s_view_lock = xSemaphoreCreateMutex();
    configASSERT(s_queue != NULL && s_code_reply != NULL && s_token_reply != NULL && s_token_lock != NULL &&
                 s_view_lock != NULL);
    net_networks_changed(&s_prov.settings); /* join the saved networks; safe before net_start */
    publish_view();
    BaseType_t created = xTaskCreate(protocol_task, "provisioning", 10240, NULL, 4, NULL);
    configASSERT(created == pdPASS);
    ESP_LOGI(TAG, "%s %s, setup state %s", name, fw,
             owl_prov_setup_state_name(owl_prov_setup_state(&s_prov)));
}
