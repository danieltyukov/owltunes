#pragma once

#include "owl_status.h"

#include "provisioning_task.h"
#include "spotify_task.h"

/* The owl's status from one snapshot each of what provisioning and the network report and of the
 * Spotify runtime. Take the snapshots once per pass so the screen and the LED agree. Any task. */
owl_status_t status_now(const provisioning_view_t *view, const spotify_task_view_t *spotify);
