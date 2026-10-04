#pragma once

#include <stdbool.h>

/* Render the active screen to a PNG, masked to the round panel (outside the circle is transparent). */
bool sim_png_write_screen(const char *path);

/* 0 when the images match: same size and at most max_fraction of pixels differ by more than
 * tolerance in any channel. 1 on mismatch, 2 when a file cannot be read. */
int sim_png_compare(const char *actual, const char *golden, int tolerance, double max_fraction);
