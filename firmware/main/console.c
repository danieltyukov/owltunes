#include "console.h"

#include <stdio.h>
#include <string.h>

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "owl_line.h"
#include "sdkconfig.h"

#if CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#else
#include "driver/uart.h"
#include "driver/uart_vfs.h"
#define CONSOLE_UART CONFIG_ESP_CONSOLE_UART_NUM
#endif

static console_line_fn s_on_line;
static owl_line_t s_lines;

/* Installing the driver sends stdout through it too, so log lines and replies take the same path.
 * Over USB-Serial/JTAG, output is dropped rather than blocking when no host reads the port. */
static void install_driver(void)
{
#if CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG
    usb_serial_jtag_driver_config_t config = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    config.rx_buffer_size = 2048;
    config.tx_buffer_size = 4096;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&config));
    usb_serial_jtag_vfs_use_driver();
#else
    ESP_ERROR_CHECK(uart_driver_install(CONSOLE_UART, 2048, 0, 0, NULL, 0));
    uart_vfs_dev_use_driver(CONSOLE_UART);
#endif
}

static int read_chunk(char *buf, size_t cap)
{
#if CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG
    return usb_serial_jtag_read_bytes(buf, (uint32_t)cap, pdMS_TO_TICKS(100));
#else
    return uart_read_bytes(CONSOLE_UART, buf, (uint32_t)cap, pdMS_TO_TICKS(100));
#endif
}

static void deliver(const char *line, void *ctx)
{
    (void)ctx;
    s_on_line(line);
}

static void reader_task(void *arg)
{
    (void)arg;
    static char chunk[256];
    while (true) {
        int n = read_chunk(chunk, sizeof chunk);
        if (n > 0) {
            owl_line_feed(&s_lines, chunk, (size_t)n, deliver, NULL);
            /* The chunk may hold a password or a login code: do not leave it in memory. */
            volatile char *p = chunk;
            for (int i = 0; i < n; i++) {
                p[i] = '\0';
            }
        }
    }
}

void owl_console_start(console_line_fn on_line)
{
    s_on_line = on_line;
    owl_line_init(&s_lines);
    install_driver();
    BaseType_t created = xTaskCreate(reader_task, "console", 6144, NULL, 5, NULL);
    configASSERT(created == pdPASS);
}

void owl_console_write(const char *line)
{
    flockfile(stdout);
    fputs(line, stdout);
    fflush(stdout);
    funlockfile(stdout);
}
