#include "console.h"

#include <stdio.h>
#include <string.h>

#include "driver/uart.h"
#include "driver/uart_vfs.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "owl_line.h"

#define CONSOLE_UART CONFIG_ESP_CONSOLE_UART_NUM

static console_line_fn s_on_line;
static owl_line_t s_lines;

static void deliver(const char *line, void *ctx)
{
    (void)ctx;
    if (strncmp(line, OWL_PROV_PREFIX, strlen(OWL_PROV_PREFIX)) == 0) {
        s_on_line(line);
    }
}

static void reader_task(void *arg)
{
    (void)arg;
    static char chunk[256];
    while (true) {
        int n = uart_read_bytes(CONSOLE_UART, chunk, sizeof chunk, pdMS_TO_TICKS(100));
        if (n > 0) {
            owl_line_feed(&s_lines, chunk, (size_t)n, deliver, NULL);
        }
    }
}

void owl_console_start(console_line_fn on_line)
{
    s_on_line = on_line;
    owl_line_init(&s_lines);
    ESP_ERROR_CHECK(uart_driver_install(CONSOLE_UART, 2048, 0, 0, NULL, 0));
    /* Send stdout through the driver too, so logs and protocol lines take the same path. */
    uart_vfs_dev_use_driver(CONSOLE_UART);
    xTaskCreate(reader_task, "console", 4096, NULL, 5, NULL);
}

void owl_console_write(const char *line)
{
    flockfile(stdout);
    fputs(line, stdout);
    fflush(stdout);
    funlockfile(stdout);
}
