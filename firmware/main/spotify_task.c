/* The Spotify runtime task. Everything below the "task" line runs on that one task, so the player
 * state and the command queue need no locks; other tasks see a copy (spotify_task_view). The gate
 * is shared with the provisioning task (api_gate.h). The runtime holds a copy of the access token
 * that the provisioning task keeps fresh, polls the playback state and sends console commands to
 * the Web API one at a time. */
#include "spotify_task.h"

#include <stdlib.h>
#include <string.h>

#include "api_gate.h"
#include "console.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "owl_cmdq.h"
#include "owl_poll.h"
#include "provisioning_task.h"
#include "spotify_api.h"
#include "spotify_auth.h"
#include "spotify_http.h"
#include "spotify_parse.h"
#include "timesync.h"

/* With no screen, console activity stands in for it: polling runs at the screen-on rate for this
 * long after the last command, then drops to the hot-standby rate (spec 9.4). */
#define AWAKE_MS (5 * 60 * 1000)
#define TOKEN_TIMEOUT_MS 40000
#define CLOCK_WAIT_MS 10000
#define IDLE_WAIT_MS 1000

static const char *TAG = "spotify";

static QueueHandle_t s_commands;
static SemaphoreHandle_t s_view_lock;
static spotify_task_view_t s_view;  /* active and player; the gate fields are read when asked */
static spotify_block_t s_view_held; /* a block the api line still shows although the gate is open */

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
    spotify_block_t held = s_view_held;
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
        if (out->block == SPOTIFY_BLOCK_NONE) {
            out->block = held; /* the LED agrees with the api line (announce) */
        }
    }
}

/* ---- task ---------------------------------------------------------------------------------- */

/* The larger buffers (about 17 KB), in PSRAM where there is some: internal RAM is scarce. The
 * runtime sends one request at a time, so one request buffer serves them all. */
typedef struct {
    owl_cmdq_t queue;
    spotify_request_t req;
    owl_cmd_t sending;  /* the command work() is sending */
    owl_cmd_t dropping; /* the command drop_queue() reports */
    owl_cmd_t taking;   /* the command take() resolves */
} runtime_buffers_t;

static runtime_buffers_t *s_buf;
static owl_player_t s_player;
static owl_player_t s_before;      /* the player before the last poll, to print only real changes */
static owl_list_page_t *s_devices; /* the last device list, NULL until the first "devices" */
static char s_token[SPOTIFY_ACCESS_TOKEN_LEN];
static int64_t s_token_expires_ms;
static uint32_t s_login_seq; /* the login s_token belongs to (provisioning_view_t.login_seq) */
static int64_t s_last_poll_ms = -1;
static int64_t s_last_command_ms = -1;
static int64_t s_awake_until_ms;
static bool s_active;
static bool s_want_devices;
static bool s_want_liked;
static bool s_confirm;          /* print the next poll even if nothing changed: it confirms a command */
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

static spotify_block_t gate_block(int64_t now)
{
    spotify_gate_t gate;
    api_gate_get(&gate);
    return spotify_gate_block(&gate, now);
}

static int32_t gate_wait_s(int64_t now)
{
    spotify_gate_t gate;
    api_gate_get(&gate);
    return spotify_gate_wait_s(&gate, now);
}

static void print_player(void)
{
    spotify_gate_t gate;
    int64_t now = now_ms();
    api_gate_get(&gate);
    write_out(owl_shell_player_line(s_out, sizeof s_out, &s_player, now, spotify_gate_link(&gate, now),
                                    spotify_gate_wait_s(&gate, now)));
}

static void forget_token(void)
{
    memset(s_token, 0, sizeof s_token);
    s_token_expires_ms = 0;
}

/* Device numbers from an earlier list may name other devices now, or another account's. */
static void forget_devices(void)
{
    if (s_devices != NULL) {
        owl_list_page_init(s_devices, OWL_LIST_NONE, NULL);
    }
}

/* Fail every queued command with error: after a refusal, older presses are stale. */
static void drop_queue(const char *error, int32_t retry_s)
{
    while (owl_cmdq_pop(&s_buf->queue, &s_buf->dropping)) {
        cmd_line("failed", owl_shell_cmd_name(s_buf->dropping.type), error, retry_s);
    }
}

/* A valid access token in s_token. The provisioning task is asked only when the copy here is
 * missing, about to expire or refused by Spotify (force), and only while the gate is open: a
 * failed refresh is tried again when the gate's wait (Retry-After or backoff) is over. */
static bool token_held(int64_t now)
{
    return s_token[0] != '\0' && s_token_expires_ms - now > SPOTIFY_REFRESH_MARGIN_MS;
}

static provisioning_token_t get_token(bool force)
{
    int64_t now = now_ms();
    if (force) {
        forget_token(); /* Spotify refused it: never hand it out again, even if no refresh can go now */
    } else if (token_held(now)) {
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
    spotify_block_t block = gate_block(now);
    if (result == PROVISIONING_TOKEN_RETRY && block != SPOTIFY_BLOCK_NONE) {
        /* No refresh may go out yet: say why and when the next one may (P18). */
        event_line("auth", "failed", "error", spotify_block_name(block), "retry_s", gate_wait_s(now));
    } else {
        event_line("auth", "failed", "error", token_error(result), NULL, 0);
    }
}

/* Send one request with a valid access token and record Spotify's answer in the gate. A 401 gets
 * one forced token refresh and one more try. Nothing goes out while the gate is closed. error
 * receives the console's error code when the outcome is not OK. A request that could not get a
 * token never went out, so no Web API answer is recorded for it (spotify_link.c recorded the token
 * endpoint's). */
static spotify_outcome_t call(const spotify_request_t *req, spotify_http_response_t *resp, const char **error)
{
    for (int attempt = 0; attempt < 2; attempt++) {
        provisioning_token_t token = get_token(attempt > 0);
        spotify_block_t block = gate_block(now_ms());
        if (block != SPOTIFY_BLOCK_NONE) {
            *error = spotify_block_name(block); /* P18: backoff, rate_limited or quota */
            return SPOTIFY_OUTCOME_WAIT;
        }
        if (token != PROVISIONING_TOKEN_OK) {
            *error = token_error(token);
            return SPOTIFY_OUTCOME_WAIT;
        }
        if (spotify_http_call(req, s_token, resp) != ESP_OK) {
            api_gate_record_web(NULL, now_ms());
            *error = "network";
            return SPOTIFY_OUTCOME_WAIT;
        }
        spotify_error_t err;
        spotify_classify_error(resp->status, resp->body, resp->len, resp->retry_after_s, &err);
        spotify_outcome_t outcome = api_gate_record_web(&err, now_ms());
        *error = spotify_error_name(err.kind);
        if (outcome != SPOTIFY_OUTCOME_REFRESH) {
            return outcome;
        }
    }
    *error = "auth"; /* refused twice, even with a fresh token */
    return SPOTIFY_OUTCOME_FAILED;
}

static void send_command(const owl_cmd_t *cmd)
{
    spotify_request_t *req = &s_buf->req;
    spotify_http_response_t resp;
    const char *name = owl_shell_cmd_name(cmd->type);
    const char *error = "";
    if (!spotify_request_for_command(cmd, req)) {
        cmd_line("failed", name, "bad_request", 0);
        return;
    }
    spotify_outcome_t outcome = call(req, &resp, &error);
    s_last_command_ms = now_ms(); /* the scheduler polls 500 ms later to confirm */
    s_confirm = true;
    if (outcome == SPOTIFY_OUTCOME_OK) {
        cmd_line("done", name, NULL, 0);
        return;
    }
    int32_t retry_s = gate_wait_s(now_ms());
    cmd_line("failed", name, error, retry_s);
    if (outcome == SPOTIFY_OUTCOME_WAIT) {
        drop_queue(error, retry_s);
    }
}

static void poll_player(void)
{
    spotify_request_t *req = &s_buf->req;
    spotify_http_response_t resp;
    const char *error = "";
    spotify_request_player_state(req);
    spotify_outcome_t outcome = call(req, &resp, &error);
    s_last_poll_ms = now_ms();
    if (outcome != SPOTIFY_OUTCOME_OK) {
        ESP_LOGW(TAG, "playback state not read: %s", error);
        return;
    }
    s_before = s_player;
    if (resp.truncated || spotify_parse_player(resp.len > 0 ? resp.body : NULL, resp.len, now_ms(),
                                               &s_player) != SPOTIFY_PARSE_OK) {
        ESP_LOGW(TAG, "could not read the playback state (%u bytes)", (unsigned)resp.len);
        return;
    }
    if (s_player.has_track && !s_player.liked_known &&
        (!s_before.has_track || strcmp(s_before.track.uri, s_player.track.uri) != 0)) {
        s_want_liked = true;
    }
    if (s_confirm || owl_shell_player_changed(&s_before, &s_player)) {
        s_confirm = false;
        print_player();
    }
}

static void check_liked(void)
{
    spotify_request_t *req = &s_buf->req;
    spotify_http_response_t resp;
    const char *error = "";
    char uri[OWL_URI_LEN];
    bool liked = false;
    s_want_liked = false;
    if (!s_player.has_track || s_player.track.kind != OWL_ITEM_TRACK ||
        !spotify_request_liked(s_player.track.uri, req)) {
        return; /* episodes and local files cannot be liked here */
    }
    memcpy(uri, s_player.track.uri, sizeof uri);
    if (call(req, &resp, &error) == SPOTIFY_OUTCOME_OK &&
        spotify_parse_liked(resp.body, resp.len, &liked) == SPOTIFY_PARSE_OK &&
        strcmp(uri, s_player.track.uri) == 0) {
        s_player.liked = liked;
        s_player.liked_known = true;
        print_player();
    } else if (error[0] != '\0') {
        ESP_LOGW(TAG, "like state not read: %s", error);
    }
}

static void fetch_devices(void)
{
    spotify_request_t *req = &s_buf->req;
    spotify_http_response_t resp;
    const char *error = "";
    const owl_fetch_t fetch = {.kind = OWL_LIST_DEVICES};
    s_want_devices = false;
    if (s_devices == NULL) {
        s_devices = heap_caps_malloc(sizeof *s_devices, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (s_devices == NULL) {
            s_devices = malloc(sizeof *s_devices);
        }
        forget_devices();
    }
    if (s_devices == NULL || !spotify_request_for_fetch(&fetch, req)) {
        event_line("devices", "failed", "error", "no_memory", NULL, 0);
        return;
    }
    if (call(req, &resp, &error) != SPOTIFY_OUTCOME_OK) {
        event_line("devices", "failed", "error", error, "retry_s", gate_wait_s(now_ms()));
        return;
    }
    if (resp.truncated ||
        spotify_parse_list(OWL_LIST_DEVICES, resp.body, resp.len, "", NULL, s_devices) != SPOTIFY_PARSE_OK) {
        forget_devices();
        event_line("devices", "failed", "error", "bad_response", NULL, 0);
        return;
    }
    for (uint16_t i = 0; i < s_devices->count; i++) {
        write_out(owl_shell_device_line(s_out, sizeof s_out, i + 1, &s_devices->items[i]));
    }
    event_line("devices", "done", NULL, NULL, "count", s_devices->count);
}

/* A console command: answered at once, or queued for work(). */
static void take(const owl_shell_cmd_t *cmd, const provisioning_view_t *view)
{
    owl_cmd_t *out = &s_buf->taking;
    int64_t now = now_ms();
    const char *name = owl_shell_verb_name(cmd->verb);
    s_awake_until_ms = now + AWAKE_MS;
    if (!s_active) {
        cmd_line("refused", name, view->linked ? "offline" : "not_linked", 0);
        return;
    }
    if (cmd->verb == OWL_SHELL_STATUS) {
        print_player();
        return;
    }
    if (cmd->verb == OWL_SHELL_AUTH) {
        report_auth(cmd->value == 1);
        return;
    }
    spotify_block_t block = gate_block(now);
    if (block != SPOTIFY_BLOCK_NONE) {
        cmd_line("refused", name, spotify_block_name(block), gate_wait_s(now));
        return;
    }
    if (cmd->verb == OWL_SHELL_DEVICES) {
        s_want_devices = true;
        return;
    }
    const char *error = owl_shell_resolve(cmd, &s_player, s_devices, out);
    if (error != NULL) {
        cmd_line("refused", name, error, 0);
    } else if (!owl_cmdq_push(&s_buf->queue, out)) {
        cmd_line("refused", name, "busy", 0);
    } else {
        owl_player_apply_optimistic(&s_player, out, now);
        cmd_line("queued", owl_shell_cmd_name(out->type), NULL, 0);
    }
}

static owl_poll_inputs_t poll_inputs(int64_t now)
{
    spotify_gate_t gate;
    api_gate_get(&gate);
    owl_poll_inputs_t in = {
        .now_ms = now,
        .asleep = false,
        .screen_on = now < s_awake_until_ms,
        .status = s_player.status,
        .remaining_ms = owl_player_remaining_ms(&s_player, now),
        .last_poll_ms = s_last_poll_ms,
        .last_command_ms = s_last_command_ms,
        .blocked_until_ms = gate.blocked_until_ms,
    };
    return in;
}

/* At most one request per pass: commands first (spec 5.2: one at a time), then what the console
 * asked for, then the scheduled poll. */
static void work(void)
{
    int64_t now = now_ms();
    if (!api_gate_open(now)) {
        return;
    }
    if (owl_cmdq_pop(&s_buf->queue, &s_buf->sending)) {
        send_command(&s_buf->sending);
    } else if (s_want_devices) {
        fetch_devices();
    } else if (s_want_liked) {
        check_liked();
    } else {
        owl_poll_inputs_t in = poll_inputs(now);
        if (owl_poll_delay_ms(&in) == 0) {
            poll_player();
        }
    }
}

static TickType_t next_wait(void)
{
    if (!s_active) {
        return pdMS_TO_TICKS(IDLE_WAIT_MS);
    }
    int64_t now = now_ms();
    owl_poll_inputs_t in = poll_inputs(now);
    int64_t delay = owl_poll_delay_ms(&in);
    if (api_gate_open(now) && (owl_cmdq_count(&s_buf->queue) > 0 || s_want_devices || s_want_liked)) {
        delay = 0;
    }
    if (delay == OWL_POLL_NEVER || delay > IDLE_WAIT_MS) {
        delay = IDLE_WAIT_MS; /* wake every second to notice logins, logouts and the network */
    }
    return pdMS_TO_TICKS(delay);
}

/* While the runtime works, an api line says when the gate closes, why (quota, rate_limited or
 * backoff, P18) and for how long, and when it opens again (ready). */
static void announce(int64_t now)
{
    spotify_block_t block = gate_block(now);
    if (s_announced && block == s_shown) {
        return;
    }
    if (s_announced && block == SPOTIFY_BLOCK_NONE && !token_held(now)) {
        return; /* open between refreshes that keep failing: say ready once a token is held again */
    }
    s_announced = true;
    s_shown = block;
    if (block == SPOTIFY_BLOCK_NONE) {
        event_line("api", "ready", NULL, NULL, NULL, 0);
    } else {
        event_line("api", spotify_block_name(block), NULL, NULL, "retry_s", gate_wait_s(now));
    }
}

static void become(bool active, const provisioning_view_t *view)
{
    s_active = active;
    s_announced = false;
    if (active) {
        s_last_poll_ms = -1; /* poll at once */
        s_last_command_ms = -1;
        s_awake_until_ms = now_ms() + AWAKE_MS;
        announce(now_ms());
        return;
    }
    const char *why = view->linked ? "offline" : "not_linked";
    drop_queue(why, 0);
    forget_token();
    forget_devices();
    spotify_http_close();
    owl_player_init(&s_player);
    s_want_devices = false;
    s_want_liked = false;
    s_confirm = false;
    event_line("api", "stopped", "error", why, NULL, 0);
}

static void publish(void)
{
    xSemaphoreTake(s_view_lock, portMAX_DELAY);
    s_view.active = s_active;
    s_view.player = s_player;
    s_view_held = s_active && s_announced ? s_shown : SPOTIFY_BLOCK_NONE;
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
            /* A new login replaced the one this token came from, maybe for another account. */
            s_login_seq = view.login_seq;
            forget_token();
            forget_devices();
            spotify_http_close();
        }
        if (ready != s_active) {
            become(ready, &view);
        }
        if (xQueueReceive(s_commands, &cmd, next_wait()) == pdTRUE) {
            take(&cmd, &view);
        }
        if (s_active) {
            work();
            announce(now_ms());
        }
        publish();
    }
}

void spotify_task_start(void)
{
    s_buf = heap_caps_calloc(1, sizeof *s_buf, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (s_buf == NULL) {
        s_buf = calloc(1, sizeof *s_buf); /* QEMU has no PSRAM */
    }
    configASSERT(s_buf != NULL);
    owl_player_init(&s_player);
    owl_cmdq_init(&s_buf->queue);
    s_view_lock = xSemaphoreCreateMutex();
    s_commands = xQueueCreate(8, sizeof(owl_shell_cmd_t));
    configASSERT(s_view_lock != NULL && s_commands != NULL);
    publish();
    BaseType_t created = xTaskCreatePinnedToCore(runtime_task, "spotify", 12288, NULL, 4, NULL, 0);
    configASSERT(created == pdPASS);
}
