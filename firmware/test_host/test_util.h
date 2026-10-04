#pragma once

#include <stdbool.h>
#include <stddef.h>

/* Read a file from OWL_FIXTURE_DIR into a malloc'd NUL-terminated buffer (caller frees) and
 * set *len. Fails the running test when the file cannot be read. */
char *read_fixture(const char *name, size_t *len);

/* True when s is well-formed UTF-8 (no truncated or stray continuation bytes). */
bool is_valid_utf8(const char *s);
