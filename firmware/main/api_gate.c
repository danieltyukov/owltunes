#include "api_gate.h"

#include "freertos/FreeRTOS.h"

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static spotify_gate_t s_gate; /* all zero: an open gate, as spotify_gate_init leaves it */

spotify_outcome_t api_gate_record_token(const spotify_error_t *err, int64_t now_ms)
{
    portENTER_CRITICAL(&s_lock);
    spotify_outcome_t outcome = spotify_gate_record_token(&s_gate, err, now_ms);
    portEXIT_CRITICAL(&s_lock);
    return outcome;
}

spotify_outcome_t api_gate_record_web(const spotify_error_t *err, int64_t now_ms)
{
    portENTER_CRITICAL(&s_lock);
    spotify_outcome_t outcome = spotify_gate_record(&s_gate, err, now_ms);
    portEXIT_CRITICAL(&s_lock);
    return outcome;
}

void api_gate_get(spotify_gate_t *out)
{
    portENTER_CRITICAL(&s_lock);
    *out = s_gate;
    portEXIT_CRITICAL(&s_lock);
}

bool api_gate_open(int64_t now_ms)
{
    spotify_gate_t gate;
    api_gate_get(&gate);
    return spotify_gate_open(&gate, now_ms);
}
