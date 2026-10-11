#include "shell.h"

#include <string.h>

#include "console.h"
#include "esp_app_desc.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "net.h"
#include "owl_prov.h"
#include "owl_shell.h"
#include "provisioning_task.h"
#include "sdkconfig.h"
#include "status.h"
#include "timesync.h"
#if CONFIG_SPIRAM
#include "esp_psram.h"
#endif

static const char *s_name;
static char s_out[OWL_SHELL_LINE_MAX + 1]; /* only the console task writes here */

static const char *reset_name(esp_reset_reason_t reason)
{
    switch (reason) {
    case ESP_RST_POWERON:
        return "poweron";
    case ESP_RST_EXT:
        return "pin";
    case ESP_RST_SW:
        return "software";
    case ESP_RST_PANIC:
        return "panic";
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT:
    case ESP_RST_WDT:
        return "watchdog";
    case ESP_RST_DEEPSLEEP:
        return "deepsleep";
    case ESP_RST_BROWNOUT:
        return "brownout";
    case ESP_RST_USB:
        return "usb";
    default:
        return "other";
    }
}

static void reply_info(void)
{
    net_info_t net;
    provisioning_view_t view;
    char utc[24] = "";
    uint32_t flash_size = 0;
    net_info(&net);
    provisioning_view(&view);
    timesync_utc(utc, sizeof utc);
    esp_flash_get_size(NULL, &flash_size);
    const esp_partition_t *running = esp_ota_get_running_partition();
    owl_status_t status = status_now(&view);
    owl_shell_info_t info = {
        .board = CONFIG_OWL_BOARD_NAME,
        .name = s_name,
        .fw = esp_app_get_description()->version,
        .uptime_s = esp_timer_get_time() / 1000000,
        .reset = reset_name(esp_reset_reason()),
        .partition = running != NULL ? running->label : "",
        .flash_kb = flash_size / 1024,
#if CONFIG_SPIRAM
        .psram_kb = (uint32_t)(esp_psram_get_size() / 1024),
#endif
        .psram_free_kb = (uint32_t)(heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024),
        .heap_free_kb = (uint32_t)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024),
        .heap_min_kb = (uint32_t)(heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL) / 1024),
        .status = owl_status_name(status),
        .led = owl_status_led(status, 0), /* the colour while lit, even for a blinking status */
        .wifi = net.state,
        .ssid = net.ssid,
        .rssi = net.rssi,
        .ip = net.ip,
        .linked = view.linked,
        .utc = utc,
    };
    if (owl_shell_info_line(s_out, sizeof s_out, &info)) {
        owl_console_write(s_out);
    }
}

/* Runs on the console task. Nothing here may block for long: @owl lines are handed to the
 * provisioning task. */
static void on_line(const char *line)
{
    if (strncmp(line, OWL_PROV_PREFIX, strlen(OWL_PROV_PREFIX)) == 0) {
        provisioning_line(line);
        return;
    }
    owl_shell_cmd_t cmd;
    owl_shell_parse(line, &cmd);
    const char *name = owl_shell_verb_name(cmd.verb);
    bool built = false;
    if (cmd.verb == OWL_SHELL_NONE) {
        return;
    } else if (cmd.verb == OWL_SHELL_UNKNOWN) {
        built = owl_shell_cmd_line(s_out, sizeof s_out, "refused", NULL, "unknown_cmd", 0);
    } else if (cmd.bad_arg) {
        built = owl_shell_cmd_line(s_out, sizeof s_out, "refused", name, "bad_arg", 0);
    } else if (cmd.verb == OWL_SHELL_HELP) {
        built = owl_shell_help_line(s_out, sizeof s_out);
    } else {
        reply_info();
    }
    if (built) {
        owl_console_write(s_out);
    }
}

void shell_start(const char *name)
{
    s_name = name;
    owl_console_start(on_line);
}
