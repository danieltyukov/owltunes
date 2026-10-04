#include "owl_gesture.h"

#include <string.h>

void owl_btn_init(owl_btn_t *b, bool double_enabled)
{
    memset(b, 0, sizeof *b);
    b->double_enabled = double_enabled;
}

owl_btn_event_t owl_btn_update(owl_btn_t *b, bool pressed, int64_t now_ms)
{
    if (pressed && !b->down) {
        owl_btn_event_t ev = OWL_BTN_NONE;
        b->down = true;
        b->hold_fired = false;
        b->down_at_ms = now_ms;
        if (b->pending_short) {
            b->pending_short = false;
            if (now_ms - b->released_at_ms <= OWL_BTN_DOUBLE_MS) {
                b->double_armed = true;
            } else {
                ev = OWL_BTN_SHORT; /* the earlier tap timed out before this press */
            }
        }
        return ev;
    }
    if (pressed) {
        if (!b->hold_fired && now_ms - b->down_at_ms >= OWL_BTN_HOLD_MS) {
            b->hold_fired = true;
            b->double_armed = false;
            return OWL_BTN_HOLD;
        }
        return OWL_BTN_NONE;
    }
    if (b->down) {
        b->down = false;
        if (b->hold_fired) {
            return OWL_BTN_HOLD_RELEASE;
        }
        if (b->double_armed) {
            b->double_armed = false;
            return OWL_BTN_DOUBLE;
        }
        if (!b->double_enabled) {
            return OWL_BTN_SHORT;
        }
        b->pending_short = true;
        b->released_at_ms = now_ms;
        return OWL_BTN_NONE;
    }
    if (b->pending_short && now_ms - b->released_at_ms > OWL_BTN_DOUBLE_MS) {
        b->pending_short = false;
        return OWL_BTN_SHORT;
    }
    return OWL_BTN_NONE;
}

void owl_ring_init(owl_ring_t *r, uint16_t steps_per_cycle)
{
    r->step_deg = 360.0f / (float)(steps_per_cycle ? steps_per_cycle : 1);
    r->accum_deg = 0.0f;
    r->last_deg = 0.0f;
    r->has_last = false;
}

int32_t owl_ring_update(owl_ring_t *r, float angle_deg)
{
    if (!r->has_last) {
        r->has_last = true;
        r->last_deg = angle_deg;
        return 0;
    }
    float delta = angle_deg - r->last_deg;
    if (delta > 180.0f) {
        delta -= 360.0f;
    } else if (delta < -180.0f) {
        delta += 360.0f;
    }
    r->last_deg = angle_deg;
    r->accum_deg += delta;
    int32_t steps = (int32_t)(r->accum_deg / r->step_deg); /* truncates toward zero */
    r->accum_deg -= (float)steps * r->step_deg;
    return steps;
}
