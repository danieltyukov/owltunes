#pragma once

#include <stdbool.h>

#include "esp_err.h"

/* Runs on the HTTP server task. Returns NULL when the owl accepted the code, else an error code. */
typedef const char *(*callback_code_fn)(const char *code, const char *state);

/* Serve http://<owl>/callback on port 80: the LAN fallback for delivering the Spotify login code. */
esp_err_t callback_server_start(callback_code_fn on_code);
/* Stop listening. When ESP-IDF cannot stop the server it keeps running: the handle is kept,
 * callback_server_running() stays true and the error is logged, so call this again later. */
esp_err_t callback_server_stop(void);
/* True while a server is started, including one that could not be stopped yet. */
bool callback_server_running(void);
