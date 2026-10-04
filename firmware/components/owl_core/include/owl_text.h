#pragma once

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Returned by owl_url_encode when the output does not fit. */
#define OWL_TEXT_OVERFLOW ((size_t)-1)

/* Copy src into dst (cap bytes including the terminator), truncating on a UTF-8 code point
 * boundary so a multi-byte character is never split. A NULL src copies "". Returns the number
 * of bytes written, not counting the terminator. */
size_t owl_utf8_copy(char *dst, size_t cap, const char *src);

/* Append src to the string already in dst with the same truncation rule. Returns the new length. */
size_t owl_utf8_append(char *dst, size_t cap, const char *src);

/* Percent-encode src for a URL query value. Unreserved characters (A-Z a-z 0-9 - . _ ~) are kept.
 * Returns the encoded length, or OWL_TEXT_OVERFLOW with dst set to "" when it does not fit. */
size_t owl_url_encode(char *dst, size_t cap, const char *src);

#ifdef __cplusplus
}
#endif
