#include "test_util.h"

#include <stdio.h>
#include <stdlib.h>

#include "unity.h"

void setUp(void)
{
}

void tearDown(void)
{
}

char *read_fixture(const char *name, size_t *len)
{
    char path[512];
    snprintf(path, sizeof path, "%s/%s", OWL_FIXTURE_DIR, name);
    FILE *f = fopen(path, "rb");
    if (f == NULL) {
        TEST_FAIL_MESSAGE(path);
    }
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = malloc((size_t)size + 1);
    TEST_ASSERT_NOT_NULL(buf);
    size_t got = fread(buf, 1, (size_t)size, f);
    fclose(f);
    buf[got] = '\0';
    *len = got;
    return buf;
}

bool is_valid_utf8(const char *s)
{
    const unsigned char *p = (const unsigned char *)s;
    while (*p) {
        int extra;
        if (*p < 0x80) {
            extra = 0;
        } else if ((*p & 0xE0) == 0xC0) {
            extra = 1;
        } else if ((*p & 0xF0) == 0xE0) {
            extra = 2;
        } else if ((*p & 0xF8) == 0xF0) {
            extra = 3;
        } else {
            return false;
        }
        p++;
        for (int i = 0; i < extra; i++, p++) {
            if ((*p & 0xC0) != 0x80) {
                return false;
            }
        }
    }
    return true;
}
