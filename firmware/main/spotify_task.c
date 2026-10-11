/* The Spotify runtime task. Everything below the "task" line runs on that one task, so its state
 * needs no locks; other tasks see a copy (spotify_task_view). It holds a copy of the access token
 * that the provisioning task keeps fresh, and answers auth and status; playback commands are refused
 * with not_ready until the runtime polls the player. */
#include "spotify_task.h"

#include <string.h>

#include "api_gate.h"
#include "console.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "provisioning_task.h"
#include "spotify_auth.h"
#include "timesync.h"

#define TOKEN_TIMEOUT_MS 40000
#define CLOCK_WAIT_MS 10000
#define IDLE_WAIT_MS 1000

static QueueHandle_t s_commands;
static SemaphoreHandle_t s_view_lock;
static spotify_task_view_t s_view; /* active and player; the gate fields are read when asked */

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

bool spotify_task_post(const owl_shell_cmd_t *cmd)
{
    return s_commands != NULL && xQueueSend(s_commands, cmd, 0) == pdTRUE;
}

void spotify_task_view(spotify_task_view_t *out)
{
    xSemaphoreTake(s_view_lock, portMAX_DELAY);
    *out = s_view;
    xSemaphoreGive(s_view_lock);
    out->link = OWL_LINK_NONE;
    out->wait_s = 0;
    out->block = SPOTIFY_BLOCK_NONE;
    if (out->active) { /* the provisioning task records token answers too, so read the gate now */
        spotify_gate_t gate;
        int64_t now = now_ms();
        api_gate_get(&gate);
        out->link = spotify_gate_link(&gate, now);
        out->wait_s = spotify_gate_wait_s(&gate, now);
        out->block = spotify_gate_block(&gate, now);
    }
}

/* ---- task ---------------------------------------------------------------------------------- */

static owl_player_t s_player;
static char s_token[SPOTIFY_ACCESS_TOKEN_LEN];
static int64_t s_token_expires_ms;
static uint32_t s_login_seq; /* the login s_token belongs to (provisioning_view_t.login_seq) */
static bool s_active;
static bool s_announced;        /* an api line has described the gate since the runtime started */
static spotify_block_t s_shown; /* the gate state that line reported */
static char s_out[OWL_SHELL_LINE_MAX + 1];

static void write_out(bool built)
{
    if (built) {
        owl_console_write(s_out);
    }
}

static void cmd_line(const char *state, const char *cmd, const char *error, int32_t retry_s)
{
    write_out(owl_shell_cmd_line(s_out, sizeof s_out, state, cmd, error, retry_s));
}

static void event_line(const char *event, const char *state, const char *key, const char *value,
                       const char *num_key, int64_t num)
{
    write_out(owl_shell_event_line(s_out, sizeof s_out, event, state, key, value, num_key, num));
}

static void forget_token(void)
{
    memset(s_token, 0, sizeof s_token);
    s_token_expires_ms = 0;
}

/* A valid access token in s_token. The provisioning task is asked only when the copy here is
 * missing, about to expire or refused by Spotify (force), and only while the gate is open: a
 * failed refresh is tried again when the gate's wait (Retry-After or backoff) is over. */
static provisioning_token_t get_token(bool force)
{
    int64_t now = now_ms();
    if (!force && s_token[0] != '\0' && s_token_expires_ms - now > SPOTIFY_REFRESH_MARGIN_MS) {
        return PROVISIONING_TOKEN_OK;
    }
    if (!api_gate_open(now)) {
        return PROVISIONING_TOKEN_RETRY;
    }
    provisioning_token_t result =
        provisioning_access_token(s_token, sizeof s_token, &s_token_expires_ms, force, TOKEN_TIMEOUT_MS);
    if (result != PROVISIONING_TOKEN_OK) {
        forget_token();
    }
    return result;
}

static const char *token_error(provisioning_token_t result)
{
    switch (result) {
    case PROVISIONING_TOKEN_NOT_LINKED:
        return "not_linked";
    case PROVISIONING_TOKEN_LOGGED_OUT:
        return "logged_out";
    case PROVISIONING_TOKEN_RETRY:
        return "network";
    case PROVISIONING_TOKEN_STORAGE:
        return "storage";
    case PROVISIONING_TOKEN_OK:
        break;
    }
    return "";
}

/* The auth line. The token itself is never printed: only whether there is one and when it expires. */
static void report_auth(bool force)
{
    provisioning_token_t result = get_token(force);
    int64_t now = now_ms();
    if (result == PROVISIONING_TOKEN_OK) {
        event_line("auth", "ok", NULL, NULL, "expires_in_s", (s_token_expires_ms - now) / 1000);
        return;
    }
    spotify_gate_t gate;
    api_gate_get(&gate);
    spotify_block_t block = spotify_gate_block(&gate, now);
    if (result == PROVISIONING_TOKEN_RETRY && block != SPOTIFY_BLOCK_NONE) {
        /* No refresh may go out yet: say why and when the next one may (P18). */
        event_line("auth", "failed", "error", spotify_block_name(block), "retry_s",
                   spotify_gate_wait_s(&gate, now));
    } else {
        event_line("auth", "failed", "error", token_error(result), NULL, 0);
    }
}

static void take(const owl_shell_cmd_t *cmd, const provisioning_view_t *view)
{
    const char *name = owl_shell_verb_name(cmd->verb);
    if (!s_active) {
        cmd_line("refused", name, view->linked ? "offline" : "not_linked", 0);
    } else if (cmd->verb == OWL_SHELL_AUTH) {
        report_auth(cmd->value == 1);
    } else if (cmd->verb == OWL_SHELL_STATUS) {
        spotify_gate_t gate;
        int64_t now = now_ms();
        api_gate_get(&gate);
        write_out(owl_shell_player_line(s_out, sizeof s_out, &s_player, now, spotify_gate_link(&gate, now),
                                        spotify_gate_wait_s(&gate, now)));
    } else {
        cmd_line("refused", name, "not_ready", 0); /* playback arrives with polling */
    }
}

/* While the runtime works, an api line says when the gate closes, why (quota, rate_limited or
 * backoff, P18) and for how long, and when it opens again (ready). */
static void announce(int64_t now)
{
    spotify_gate_t gate;
    api_gate_get(&gate);
    spotify_block_t block = spotify_gate_block(&gate, now);
    if (s_announced && block == s_shown) {
        return;
    }
    s_announced = true;
    s_shown = block;
    if (block == SPOTIFY_BLOCK_NONE) {
        event_line("api", "ready", NULL, NULL, NULL, 0);
    } else {
        event_line("api", spotify_block_name(block), NULL, NULL, "retry_s", spotify_gate_wait_s(&gate, now));
    }
}

static void become(bool active, const provisioning_view_t *view)
{
    s_active = active;
    s_announced = false;
    if (active) {
        announce(now_ms());
        return;
    }
    forget_token();
    owl_player_init(&s_player);
    event_line("api", "stopped", "error", view->linked ? "offline" : "not_linked", NULL, 0);
}

static void publish(void)
{
    xSemaphoreTake(s_view_lock, portMAX_DELAY);
    s_view.active = s_active;
    s_view.player = s_player;
    xSemaphoreGive(s_view_lock);
}

static void runtime_task(void *arg)
{
    (void)arg;
    static provisioning_view_t view;
    static owl_shell_cmd_t cmd;
    bool clock_checked = false;
    while (true) {
        provisioning_view(&view);
        bool ready = view.linked && view.network_up;
        if (ready && !clock_checked) {
            /* Real timestamps in logs and lines before the runtime starts; TLS does not need the
             * clock, so a network that blocks NTP only delays this once. Then look again. */
            clock_checked = true;
            timesync_wait(CLOCK_WAIT_MS);
            continue;
        }
        if (view.login_seq != s_login_seq) {
            s_login_seq = view.login_seq;
            forget_token(); /* a new login replaced the one this token came from */
        }
        if (ready != s_active) {
            become(ready, &view);
        } else if (s_active) {
            announce(now_ms());
        }
        if (xQueueReceive(s_commands, &cmd, pdMS_TO_TICKS(IDLE_WAIT_MS)) == pdTRUE) {
            take(&cmd, &view);
        }
        publish();
    }
}

void spotify_task_start(void)
{
    owl_player_init(&s_player);
    s_view_lock = xSemaphoreCreateMutex();
    s_commands = xQueueCreate(8, sizeof(owl_shell_cmd_t));
    configASSERT(s_view_lock != NULL && s_commands != NULL);
    publish();
    BaseType_t created = xTaskCreatePinnedToCore(runtime_task, "spotify", 12288, NULL, 4, NULL, 0);
    configASSERT(created == pdPASS);
}
