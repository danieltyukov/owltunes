#include "owl_line.h"

void owl_line_init(owl_line_t *l)
{
    l->len = 0;
    l->discard = false;
}

void owl_line_feed(owl_line_t *l, const char *data, size_t len, owl_line_fn on_line, void *ctx)
{
    for (size_t i = 0; i < len; i++) {
        char c = data[i];
        if (c == '\n' || c == '\r') { /* CR LF, LF, or a bare CR from terminals such as idf.py monitor */
            if (!l->discard && l->len > 0) {
                l->buf[l->len] = '\0';
                on_line(l->buf, ctx);
                /* A line can carry a password or a login code: leave none of it behind. */
                volatile char *p = l->buf;
                for (size_t k = 0; k <= l->len; k++) {
                    p[k] = '\0';
                }
            }
            l->len = 0;
            l->discard = false;
        } else if (c == '\0' || l->len == sizeof l->buf - 1) {
            l->discard = true;
        } else if (!l->discard) {
            l->buf[l->len++] = c;
        }
    }
}
