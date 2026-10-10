#include <stdio.h>
#include <string.h>

#include "owl_crypto.h"
#include "test_util.h"
#include "unity.h"

static void hex(const uint8_t *bytes, size_t len, char *out)
{
    for (size_t i = 0; i < len; i++) {
        sprintf(out + 2 * i, "%02x", bytes[i]);
    }
}

static void expect_sha256(const char *message, size_t len, const char *expected_hex)
{
    uint8_t digest[32];
    char text[65];
    owl_sha256((const uint8_t *)message, len, digest);
    hex(digest, 32, text);
    TEST_ASSERT_EQUAL_STRING(expected_hex, text);
}

static void test_sha256_known_vectors(void)
{
    expect_sha256("", 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    expect_sha256("abc", 3, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    /* 56 bytes: the length no longer fits in the first padding block. */
    expect_sha256("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq", 56,
                  "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
    char sixty_four[65];
    memset(sixty_four, 'a', 64);
    sixty_four[64] = '\0';
    expect_sha256(sixty_four, 64, "ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb");
}

static void test_base64url_rfc4648_vectors(void)
{
    static const char *const in[] = {"", "f", "fo", "foo", "foob", "fooba", "foobar"};
    static const char *const out[] = {"", "Zg", "Zm8", "Zm9v", "Zm9vYg", "Zm9vYmE", "Zm9vYmFy"};
    char buf[16];
    for (int i = 0; i < 7; i++) {
        size_t n = owl_base64url(buf, sizeof buf, (const uint8_t *)in[i], strlen(in[i]));
        TEST_ASSERT_EQUAL_STRING(out[i], buf);
        TEST_ASSERT_EQUAL_UINT(strlen(out[i]), n);
    }
}

static void test_base64url_uses_url_alphabet(void)
{
    static const uint8_t bytes[] = {0xfb, 0xff};
    char buf[8];
    owl_base64url(buf, sizeof buf, bytes, sizeof bytes);
    TEST_ASSERT_EQUAL_STRING("-_8", buf);
}

static void test_base64url_overflow(void)
{
    char buf[4];
    TEST_ASSERT_EQUAL(OWL_TEXT_OVERFLOW, owl_base64url(buf, sizeof buf, (const uint8_t *)"foo", 3));
    TEST_ASSERT_EQUAL_STRING("", buf);
}

/* RFC 7636 appendix B: the octets, the verifier they encode to, and its S256 challenge. */
static void test_pkce_rfc7636_example(void)
{
    static const uint8_t octets[32] = {116, 24,  223, 180, 151, 153, 224, 37,  79,  250, 96,
                                       125, 216, 173, 187, 186, 22,  212, 37,  77,  105, 214,
                                       191, 240, 91,  88,  5,   88,  83,  132, 141, 121};
    char verifier[64], challenge[64];
    uint8_t digest[32];
    owl_base64url(verifier, sizeof verifier, octets, sizeof octets);
    TEST_ASSERT_EQUAL_STRING("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk", verifier);
    owl_sha256((const uint8_t *)verifier, strlen(verifier), digest);
    owl_base64url(challenge, sizeof challenge, digest, sizeof digest);
    TEST_ASSERT_EQUAL_STRING("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", challenge);
}

static void test_ct_streq(void)
{
    TEST_ASSERT_TRUE(owl_ct_streq("abc.def", "abc.def"));
    TEST_ASSERT_FALSE(owl_ct_streq("abc.def", "abc.deg"));
    TEST_ASSERT_FALSE(owl_ct_streq("abc", "abcd"));
    TEST_ASSERT_FALSE(owl_ct_streq(NULL, "abc"));
    TEST_ASSERT_TRUE(owl_ct_streq("", ""));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_sha256_known_vectors);
    RUN_TEST(test_base64url_rfc4648_vectors);
    RUN_TEST(test_base64url_uses_url_alphabet);
    RUN_TEST(test_base64url_overflow);
    RUN_TEST(test_pkce_rfc7636_example);
    RUN_TEST(test_ct_streq);
    return UNITY_END();
}
