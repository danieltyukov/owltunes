#include "status.h"

owl_status_t status_now(const provisioning_view_t *view, const spotify_task_view_t *spotify)
{
    owl_status_inputs_t in = {
        .has_networks = view->n_networks > 0 || view->network_up, /* QEMU's Ethernet counts */
        .online = view->network_up,
        .linked = view->linked,
        .linking = view->mode == OWL_UI_SETUP_LINKING,
        .log_in_again = view->mode == OWL_UI_SETUP_RELINK,
        .link = spotify->link, /* OWL_LINK_BLE during a quota lockout */
        .rate_limited = spotify->block == SPOTIFY_BLOCK_RATE_LIMITED,
        .backoff = spotify->block == SPOTIFY_BLOCK_BACKOFF, /* P18: not shown as rate_limited */
        .player = spotify->player.status,
    };
    return owl_status_of(&in);
}
