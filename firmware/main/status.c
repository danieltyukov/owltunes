#include "status.h"

#include "provisioning_task.h"

owl_status_t status_now(const provisioning_view_t *view)
{
    owl_status_inputs_t in = {
        .has_networks = view->n_networks > 0 || view->network_up, /* QEMU's Ethernet counts */
        .online = view->network_up,
        .linked = view->linked,
        .linking = view->mode == OWL_UI_SETUP_LINKING,
        .log_in_again = view->mode == OWL_UI_SETUP_RELINK,
        .link = OWL_LINK_API, /* nothing talks to the Web API yet, so nothing can block it */
        .rate_limited = false,
        .backoff = false,
        .player = OWL_PLAYER_UNKNOWN,
    };
    return owl_status_of(&in);
}
