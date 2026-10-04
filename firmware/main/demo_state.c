#include "demo_state.h"

#include "esp_log.h"
#include "spotify_parse.h"

static const char *TAG = "demo";

/* A trimmed GET /v1/me/player response, parsed with the real parser so cJSON and the Spotify
 * layer are exercised on the target. */
static const char DEMO_PLAYER_JSON[] =
    "{\"device\":{\"id\":\"demo\",\"is_active\":true,\"name\":\"Pixel 9\",\"type\":\"Smartphone\","
    "\"supports_volume\":false,\"volume_percent\":64},\"is_playing\":true,\"progress_ms\":42000,"
    "\"shuffle_state\":false,\"repeat_state\":\"off\","
    "\"item\":{\"type\":\"track\",\"name\":\"Night Flight\",\"uri\":\"spotify:track:6rqhFgbbKwnb9MLmUQDhG6\","
    "\"duration_ms\":215000,\"artists\":[{\"name\":\"The Barn Owls\"},{\"name\":\"Luna Feathers\"}],"
    "\"album\":{\"name\":\"Moonlit Barn\",\"images\":[]}}}";

void demo_state_load(owl_app_t *app, owl_player_t *player, int64_t now_ms)
{
    owl_app_set_link(app, OWL_LINK_API, false);
    spotify_parse_result_t r = spotify_parse_player(DEMO_PLAYER_JSON, sizeof DEMO_PLAYER_JSON - 1, now_ms, player);
    ESP_LOGI(TAG, "demo player parsed: %s", r == SPOTIFY_PARSE_OK ? "ok" : "failed");
}
