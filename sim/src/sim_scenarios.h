#pragma once

#include <stddef.h>

#include "owl_app.h"
#include "owl_model.h"
#include "owl_ui.h"

/* The fixture playlists are owned by this user id. */
#define SIM_USER_ID "owlfan"

typedef struct {
    owl_app_t app;
    owl_player_t player;
    owl_list_page_t list;
    owl_ui_inputs_t inputs;
    int64_t now_ms;
} sim_world_t;

typedef struct {
    const char *name;
    void (*setup)(sim_world_t *w);
} sim_scenario_t;

const sim_scenario_t *sim_scenario_find(const char *name);
size_t sim_scenario_count(void);
const sim_scenario_t *sim_scenario_at(size_t index);

void sim_load_player(sim_world_t *w, const char *fixture);
void sim_load_list(sim_world_t *w, owl_list_kind_t kind, const char *fixture, const char *source_uri);
void sim_input(sim_world_t *w, owl_input_kind_t kind, int32_t steps);
