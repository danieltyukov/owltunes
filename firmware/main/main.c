#include <stdbool.h>
#include <stdio.h>

#include "bsp.h"
#include "demo_state.h"
#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lvgl.h"
#include "net.h"
#include "owl_app.h"
#include "owl_ui.h"
#include "provisioning_task.h"
#include "settings_store.h"

static const char *TAG = "owltunes";

static uint32_t tick_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000);
}

/* "OwlTunes-1A2B" from the last two bytes of the factory MAC, so two owls in one room differ. */
static void owl_name(char *out, size_t cap)
{
    uint8_t mac[6] = {0};
    esp_efuse_mac_get_default(mac);
    snprintf(out, cap, "OwlTunes-%02X%02X", mac[4], mac[5]);
}

void app_main(void)
{
    static owl_app_t app;
    static owl_player_t player;
    static char name[24];
    static char setup_url[192];

    ESP_ERROR_CHECK(settings_store_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    owl_name(name, sizeof name);
    snprintf(setup_url, sizeof setup_url, "%s?owl=%s", CONFIG_OWL_SETUP_URL, name);
    provisioning_start(name, esp_app_get_description()->version);
    net_start(provisioning_network);

    lv_init();
    lv_tick_set_cb(tick_ms);
    lv_display_t *disp = bsp_display_init();

    owl_app_init(&app);
    owl_player_init(&player);
    demo_state_load(&app, &player, esp_timer_get_time() / 1000);

    owl_ui_t *ui = owl_ui_create(disp);
    owl_ui_inputs_t inputs = {
        .art = NULL, .battery_percent = 100, .charging = true, .wifi = false, .ble = false};
    provisioning_view_t view;

    bool announced = false;
    while (true) {
        provisioning_view(&view);
        inputs.wifi = view.network_up;
        inputs.setup =
            (owl_ui_setup_t){view.mode, setup_url, name, view.error[0] != '\0' ? view.error : NULL};
        owl_ui_render(ui, &app, &player, &inputs, esp_timer_get_time() / 1000);
        uint32_t wait = lv_timer_handler();
        if (!announced) {
            ESP_LOGI(TAG, "OWL_BOOT_OK board=%s track=\"%s\" name=%s", CONFIG_OWL_BOARD_NAME,
                     player.track.title, name);
            announced = true;
        }
        vTaskDelay(pdMS_TO_TICKS(wait < 5 ? 5 : (wait > 50 ? 50 : wait)));
    }
}
