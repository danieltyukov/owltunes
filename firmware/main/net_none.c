/* Boards whose network is not written yet: never online. Saved Wi-Fi networks are only stored. */
#include <string.h>

#include "esp_log.h"
#include "net.h"

static const char *TAG = "net";

void net_start(net_change_fn on_change)
{
    (void)on_change;
    ESP_LOGW(TAG, "this board has no network support yet");
}

void net_networks_changed(const owl_settings_t *settings)
{
    ESP_LOGI(TAG, "%u Wi-Fi network(s) saved; this board cannot join them yet",
             (unsigned)settings->n_networks);
}

void net_info(net_info_t *out)
{
    memset(out, 0, sizeof *out);
    out->state = "off";
}
