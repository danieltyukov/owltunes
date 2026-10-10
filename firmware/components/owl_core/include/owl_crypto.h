#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "owl_text.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Fill buf with cryptographically secure random bytes (esp_fill_random on the owl). */
typedef void (*owl_random_fn)(uint8_t *buf, size_t len);

/* SHA-256 of data. Used once per login for the PKCE code challenge. */
void owl_sha256(const uint8_t *data, size_t len, uint8_t out[32]);

/* Base64url (RFC 4648 section 5) without padding. Returns the encoded length, or
 * OWL_TEXT_OVERFLOW with dst set to "" when it does not fit in cap bytes. */
size_t owl_base64url(char *dst, size_t cap, const uint8_t *src, size_t len);

/* String equality whose running time does not depend on where the strings differ. */
bool owl_ct_streq(const char *a, const char *b);

#ifdef __cplusplus
}
#endif
