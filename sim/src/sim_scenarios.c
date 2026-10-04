#include "sim_scenarios.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "sim_art.h"
#include "spotify_parse.h"

static char *read_fixture_file(const char *name, size_t *len)
{
    char path[512];
    snprintf(path, sizeof path, "%s/%s", OWL_FIXTURE_DIR, name);
    FILE *f = fopen(path, "rb");
    if (f == NULL) {
        fprintf(stderr, "missing fixture %s\n", path);
        exit(2);
    }
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = malloc((size_t)size + 1);
    *len = fread(buf, 1, (size_t)size, f);
    buf[*len] = '\0';
    fclose(f);
    return buf;
}

void sim_load_player(sim_world_t *w, const char *fixture)
{
    size_t len;
    char *json = read_fixture_file(fixture, &len);
    if (spotify_parse_player(json, len, w->now_ms, &w->player) != SPOTIFY_PARSE_OK) {
        fprintf(stderr, "cannot parse %s\n", fixture);
        exit(2);
    }
    free(json);
}

void sim_load_list(sim_world_t *w, owl_list_kind_t kind, const char *fixture, const char *source_uri)
{
    size_t len;
    char *json = read_fixture_file(fixture, &len);
    if (spotify_parse_list(kind, json, len, SIM_USER_ID, source_uri, &w->list) != SPOTIFY_PARSE_OK) {
        fprintf(stderr, "cannot parse %s\n", fixture);
        exit(2);
    }
    free(json);
}

void sim_input(sim_world_t *w, owl_input_kind_t kind, int32_t steps)
{
    owl_effects_t fx;
    owl_input_t in = {kind, steps};
    owl_app_handle(&w->app, &w->player, &in, w->now_ms, &fx);
}

static void base(sim_world_t *w)
{
    memset(w, 0, sizeof *w);
    owl_app_init(&w->app);
    owl_app_set_link(&w->app, OWL_LINK_API, true);
    owl_player_init(&w->player);
    w->inputs.battery_percent = 82;
    w->inputs.wifi = true;
    w->inputs.ble = true;
    w->now_ms = 100000;
}

static void no_device(sim_world_t *w)
{
    base(w);
    spotify_parse_player(NULL, 0, w->now_ms, &w->player);
}

static void now_playing(sim_world_t *w)
{
    base(w);
    sim_load_player(w, "player_track.json");
    w->player.liked = true;
    w->inputs.art = sim_art_for(w->player.track.uri);
}

static void now_playing_unicode(sim_world_t *w)
{
    base(w);
    sim_load_player(w, "player_unicode_paused.json");
    w->inputs.art = sim_art_for(w->player.track.uri);
}

static void now_playing_volume(sim_world_t *w)
{
    now_playing(w);
    w->player.device.volume_percent = 64;
    w->app.volume_overlay_until_ms = w->now_ms + 500;
}

static void offline(sim_world_t *w)
{
    base(w);
    owl_app_set_link(&w->app, OWL_LINK_NONE, true);
    w->inputs.wifi = false;
}

static void ad_break(sim_world_t *w)
{
    base(w);
    sim_load_player(w, "player_ad.json");
}

static const sim_scenario_t SCENARIOS[] = {
    {"no_device", no_device},
    {"now_playing", now_playing},
    {"now_playing_unicode", now_playing_unicode},
    {"now_playing_volume", now_playing_volume},
    {"offline", offline},
    {"ad_break", ad_break},
};

size_t sim_scenario_count(void)
{
    return sizeof SCENARIOS / sizeof SCENARIOS[0];
}

const sim_scenario_t *sim_scenario_at(size_t index)
{
    return index < sim_scenario_count() ? &SCENARIOS[index] : NULL;
}

const sim_scenario_t *sim_scenario_find(const char *name)
{
    for (size_t i = 0; i < sim_scenario_count(); i++) {
        if (strcmp(SCENARIOS[i].name, name) == 0) {
            return &SCENARIOS[i];
        }
    }
    return NULL;
}
