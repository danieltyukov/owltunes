#include <stdbool.h>

#include "board.h"
#include "demo_state.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lvgl.h"
#include "owl_app.h"
#include "owl_ui.h"

static const char *TAG = "owltunes";

static uint32_t tick_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000);
}

void app_main(void)
{
    static owl_app_t app;
    static owl_player_t player;

    lv_init();
    lv_tick_set_cb(tick_ms);
    lv_display_t *disp = board_display_init();

    owl_app_init(&app);
    owl_player_init(&player);
    demo_state_load(&app, &player, esp_timer_get_time() / 1000);

    owl_ui_t *ui = owl_ui_create(disp);
    owl_ui_inputs_t inputs = {.art = NULL, .battery_percent = 100, .charging = true, .wifi = false, .ble = false};

    bool announced = false;
    while (true) {
        owl_ui_render(ui, &app, &player, &inputs, esp_timer_get_time() / 1000);
        uint32_t wait = lv_timer_handler();
        if (!announced) {
            ESP_LOGI(TAG, "OWL_BOOT_OK track=\"%s\"", player.track.title);
            announced = true;
        }
        vTaskDelay(pdMS_TO_TICKS(wait < 5 ? 5 : (wait > 50 ? 50 : wait)));
    }
}
