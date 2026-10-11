#pragma once

#include "owl_status.h"

#include "provisioning_task.h"

/* The owl's status from one snapshot of what provisioning and the network report. Take the
 * snapshot once per pass so the screen and the LED agree. Any task. */
owl_status_t status_now(const provisioning_view_t *view);
