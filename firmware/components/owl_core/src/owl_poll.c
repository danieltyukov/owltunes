#include "owl_poll.h"

int64_t owl_poll_delay_ms(const owl_poll_inputs_t *in)
{
    if (in->asleep) {
        return OWL_POLL_NEVER;
    }
    bool playing = in->status == OWL_PLAYER_PLAYING;
    int64_t due;
    if (in->last_poll_ms < 0) {
        due = in->now_ms;
    } else if (in->last_command_ms >= 0 && in->last_command_ms > in->last_poll_ms) {
        due = in->last_command_ms + OWL_POLL_AFTER_COMMAND_MS;
    } else if (in->screen_on) {
        due = in->last_poll_ms + (playing ? OWL_POLL_PLAYING_MS : OWL_POLL_IDLE_MS);
        if (playing && in->remaining_ms > 0) {
            int64_t track_end = in->now_ms + in->remaining_ms + OWL_POLL_TRACK_END_SLACK_MS;
            if (track_end < due) {
                due = track_end;
            }
        }
    } else {
        if (!playing) {
            return OWL_POLL_NEVER;
        }
        int64_t earliest = in->last_poll_ms + OWL_POLL_STANDBY_MIN_MS;
        due = in->remaining_ms > 0 ? in->now_ms + in->remaining_ms + OWL_POLL_TRACK_END_SLACK_MS : earliest;
        if (due < earliest) {
            due = earliest;
        }
    }
    if (in->blocked_until_ms > due) {
        due = in->blocked_until_ms;
    }
    int64_t delay = due - in->now_ms;
    return delay < 0 ? 0 : delay;
}
