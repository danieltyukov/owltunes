#pragma once

#include <stdint.h>

#include "owl_app.h"
#include "owl_model.h"

/* Fill app and player with a fixed demo track until the Spotify client exists (P3). */
void demo_state_load(owl_app_t *app, owl_player_t *player, int64_t now_ms);
