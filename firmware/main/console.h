#pragma once

/* Runs on the console task with each complete line that starts with OWL_PROV_PREFIX. */
typedef void (*console_line_fn)(const char *line);

/* Take over the console's input and start the reader task. Log output keeps working. The console
 * is the USB-Serial/JTAG port on boards configured for it, else the console UART. */
void owl_console_start(console_line_fn on_line);

/* Write one whole line ("...\n") so it never interleaves with log output. */
void owl_console_write(const char *line);
