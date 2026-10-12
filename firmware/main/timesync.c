#include "timesync.h"

#include <stdatomic.h>
#include <sys/time.h>
#include <time.h>

#include "console.h"
#include "esp_log.h"
#include "esp_netif_sntp.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "owl_shell.h"

static const char *TAG = "time";
static atomic_bool s_synced;
static TaskHandle_t s_task;

/* Runs on the lwIP task after every successful sync, whose stack is small (3072 bytes): it only sets
 * the flag and wakes the announcer, which does the logging and the JSON. */
static void on_sync(struct timeval *tv)
{
    (void)tv;
    atomic_store(&s_synced, true);
    if (s_task != NULL) {
        xTaskNotifyGive(s_task);
    }
}

/* The owl's own task for the "time synced" line, once per sync. */
static void announce_task(void *arg)
{
    (void)arg;
    char utc[24];
    char line[128];
    while (true) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (timesync_utc(utc, sizeof utc)) {
            ESP_LOGI(TAG, "clock set to %s", utc);
            if (owl_shell_event_line(line, sizeof line, "time", "synced", "utc", utc, NULL, 0)) {
                owl_console_write(line);
            }
        }
    }
}

void timesync_start(void)
{
    if (xTaskCreate(announce_task, "timesync", 3072, NULL, 3, &s_task) != pdPASS) {
        ESP_LOGW(TAG, "no task for the time line; the clock is still set");
    }
    esp_sntp_config_t config =
        ESP_NETIF_SNTP_DEFAULT_CONFIG_MULTIPLE(2, ESP_SNTP_SERVER_LIST("time.google.com", "pool.ntp.org"));
    config.start = false; /* started by timesync_network_up */
    config.wait_for_sync = false;
    config.sync_cb = on_sync;
    ESP_ERROR_CHECK(esp_netif_sntp_init(&config));
}

void timesync_network_up(void)
{
    esp_err_t err = esp_netif_sntp_start();
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "could not start NTP: %s", esp_err_to_name(err));
    }
}

bool timesync_done(void)
{
    return atomic_load(&s_synced);
}

bool timesync_wait(uint32_t timeout_ms)
{
    for (uint32_t waited = 0; !timesync_done() && waited < timeout_ms; waited += 100) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    return timesync_done();
}

bool timesync_utc(char *out, size_t cap)
{
    if (!timesync_done()) {
        return false;
    }
    time_t now = time(NULL);
    struct tm tm;
    gmtime_r(&now, &tm);
    return strftime(out, cap, "%Y-%m-%dT%H:%M:%SZ", &tm) > 0;
}
