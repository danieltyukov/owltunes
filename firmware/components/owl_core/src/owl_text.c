#include "owl_text.h"

#include <stdbool.h>
#include <string.h>

size_t owl_utf8_copy(char *dst, size_t cap, const char *src)
{
    if (dst == NULL || cap == 0) {
        return 0;
    }
    if (src == NULL) {
        dst[0] = '\0';
        return 0;
    }
    size_t len = strlen(src);
    size_t n = len < cap - 1 ? len : cap - 1;
    if (n < len) {
        /* src[n] is the first byte left out. If it continues a sequence, drop that whole sequence. */
        while (n > 0 && ((unsigned char)src[n] & 0xC0) == 0x80) {
            n--;
        }
    }
    memcpy(dst, src, n);
    dst[n] = '\0';
    return n;
}

size_t owl_utf8_append(char *dst, size_t cap, const char *src)
{
    if (dst == NULL || cap == 0) {
        return 0;
    }
    size_t len = strlen(dst);
    if (len + 1 >= cap) {
        return len;
    }
    return len + owl_utf8_copy(dst + len, cap - len, src);
}

static bool is_unreserved(unsigned char c)
{
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '.' ||
           c == '_' || c == '~';
}

size_t owl_url_encode(char *dst, size_t cap, const char *src)
{
    static const char hex[] = "0123456789ABCDEF";
    if (dst == NULL || cap == 0) {
        return OWL_TEXT_OVERFLOW;
    }
    size_t o = 0;
    for (const unsigned char *p = (const unsigned char *)(src ? src : ""); *p; p++) {
        size_t need = is_unreserved(*p) ? 1 : 3;
        if (o + need >= cap) {
            dst[0] = '\0';
            return OWL_TEXT_OVERFLOW;
        }
        if (need == 1) {
            dst[o++] = (char)*p;
        } else {
            dst[o++] = '%';
            dst[o++] = hex[*p >> 4];
            dst[o++] = hex[*p & 0x0F];
        }
    }
    dst[o] = '\0';
    return o;
}
