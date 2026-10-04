#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OWL_BTN_HOLD_MS 450
#define OWL_BTN_DOUBLE_MS 300

typedef enum { OWL_BTN_NONE, OWL_BTN_SHORT, OWL_BTN_DOUBLE, OWL_BTN_HOLD, OWL_BTN_HOLD_RELEASE } owl_btn_event_t;

typedef struct {
    bool double_enabled;
    bool down;
    bool hold_fired;
    bool pending_short; /* a short press waiting to see if a second one follows */
    bool double_armed;  /* the current press is the second of a double */
    int64_t down_at_ms;
    int64_t released_at_ms;
} owl_btn_t;

void owl_btn_init(owl_btn_t *b, bool double_enabled);

/* Feed the button state on every edge and at least every 20 ms. Returns at most one event. */
owl_btn_event_t owl_btn_update(owl_btn_t *b, bool pressed, int64_t now_ms);

typedef struct {
    float step_deg;
    float accum_deg;
    float last_deg;
    bool has_last;
} owl_ring_t;

/* steps_per_cycle: haptic detents per full cycle of the sensor angle. */
void owl_ring_init(owl_ring_t *r, uint16_t steps_per_cycle);

/* angle_deg: sensor angle in [0, 360). Returns whole steps moved since the last call,
 * positive clockwise. The first call only records the starting angle. */
int32_t owl_ring_update(owl_ring_t *r, float angle_deg);

#ifdef __cplusplus
}
#endif
