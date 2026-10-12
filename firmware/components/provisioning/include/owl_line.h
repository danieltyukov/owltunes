#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "owl_prov.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Reassembles a byte stream (the console, a Bluetooth characteristic) into lines. A line longer
 * than OWL_PROV_LINE_MAX - 1 bytes, or one containing a NUL byte, is dropped whole; a line ends at "\n",
 * "\r" or "\r\n"; empty lines are skipped. The buffer is cleared after
 * each line has been handed over, so the callback must copy what it keeps. */
typedef struct {
    char buf[OWL_PROV_LINE_MAX];
    size_t len;
    bool discard; /* the current line is bad: skip to the next newline */
} owl_line_t;

typedef void (*owl_line_fn)(const char *line, void *ctx);

void owl_line_init(owl_line_t *l);
void owl_line_feed(owl_line_t *l, const char *data, size_t len, owl_line_fn on_line, void *ctx);

#ifdef __cplusplus
}
#endif
