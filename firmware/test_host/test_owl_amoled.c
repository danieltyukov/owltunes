#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "owl_co5300.h"
#include "owl_touch.h"
#include "test_util.h"
#include "unity.h"

static void test_command_words_frame_the_command_in_the_middle_bytes(void)
{
    TEST_ASSERT_EQUAL_HEX32(0x02002A00, owl_co5300_cmd_word(OWL_CO5300_OP_WRITE_CMD, OWL_CO5300_CASET));
    TEST_ASSERT_EQUAL_HEX32(0x32002C00, owl_co5300_cmd_word(OWL_CO5300_OP_WRITE_PIXELS, OWL_CO5300_RAMWR));
}

static void test_window_shifts_columns_by_the_offset(void)
{
    owl_co5300_window_t w;
    owl_co5300_window(100, 40, 201, 79, 6, &w);
    const uint8_t caset[4] = {0x00, 106, 0x00, 207};
    const uint8_t raset[4] = {0x00, 40, 0x00, 79};
    TEST_ASSERT_EQUAL_HEX8_ARRAY(caset, w.caset, 4);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(raset, w.raset, 4);

    owl_co5300_window(400, 300, 465, 465, 6, &w);
    const uint8_t caset_hi[4] = {0x01, 0x96, 0x01, 0xD7}; /* 406 to 471 */
    const uint8_t raset_hi[4] = {0x01, 0x2C, 0x01, 0xD1}; /* 300 to 465 */
    TEST_ASSERT_EQUAL_HEX8_ARRAY(caset_hi, w.caset, 4);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(raset_hi, w.raset, 4);
}

static const owl_co5300_cmd_t *find(const owl_co5300_cmd_t *table, size_t len, uint8_t cmd)
{
    for (size_t i = 0; i < len; i++) {
        if (table[i].cmd == cmd) {
            return &table[i];
        }
    }
    return NULL;
}

/* The init table's full-screen window must be the one the driver computes for the whole frame, so
 * the offset in every later window agrees with the one the table sets up. */
static void check_table(const owl_co5300_cmd_t *table, size_t len, int32_t col_offset)
{
    owl_co5300_window_t full;
    owl_co5300_window(0, 0, OWL_CO5300_RES - 1, OWL_CO5300_RES - 1, col_offset, &full);
    const owl_co5300_cmd_t *caset = find(table, len, OWL_CO5300_CASET);
    const owl_co5300_cmd_t *raset = find(table, len, OWL_CO5300_RASET);
    TEST_ASSERT_NOT_NULL(caset);
    TEST_ASSERT_NOT_NULL(raset);
    TEST_ASSERT_EQUAL(4, caset->len);
    TEST_ASSERT_EQUAL(4, raset->len);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(full.caset, caset->data, 4);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(full.raset, raset->data, 4);

    const owl_co5300_cmd_t *colmod = find(table, len, 0x3A);
    TEST_ASSERT_NOT_NULL(colmod);
    TEST_ASSERT_EQUAL_HEX8(0x55, colmod->data[0]); /* RGB565, what LVGL renders */

    for (size_t i = 0; i < len; i++) {
        TEST_ASSERT_TRUE(table[i].len <= sizeof table[i].data);
        TEST_ASSERT_NOT_EQUAL(OWL_CO5300_MADCTL, table[i].cmd); /* left to the OWL_LCD_BGR option */
    }
    /* Sleep out, its wait, then display on as the last command. */
    TEST_ASSERT_EQUAL_HEX8(0x29, table[len - 1].cmd);
    TEST_ASSERT_EQUAL_HEX8(0x11, table[len - 2].cmd);
    TEST_ASSERT_TRUE(table[len - 2].delay_ms >= 60);
}

static void test_viewe_table(void)
{
    check_table(owl_co5300_init_viewe, owl_co5300_init_viewe_len, OWL_CO5300_VIEWE_COL_OFFSET);
    TEST_ASSERT_EQUAL(11, owl_co5300_init_viewe_len);
    /* 01 D7, not the 01 DD of VIEWE's C array. */
    const owl_co5300_cmd_t *caset = find(owl_co5300_init_viewe, owl_co5300_init_viewe_len, OWL_CO5300_CASET);
    TEST_ASSERT_EQUAL_HEX8(0xD7, caset->data[3]);
    TEST_ASSERT_EQUAL_HEX8(0xFE, owl_co5300_init_viewe[0].cmd);
    TEST_ASSERT_EQUAL_HEX8(0x00, owl_co5300_init_viewe[0].data[0]);
}

static void test_waveshare_table(void)
{
    check_table(owl_co5300_init_waveshare_175, owl_co5300_init_waveshare_175_len,
                OWL_CO5300_WAVESHARE_175_COL_OFFSET);
    TEST_ASSERT_EQUAL(14, owl_co5300_init_waveshare_175_len);
}

static void test_offsets_keep_windows_even(void)
{
    TEST_ASSERT_EQUAL(0, OWL_CO5300_VIEWE_COL_OFFSET % 2);
    TEST_ASSERT_EQUAL(0, OWL_CO5300_WAVESHARE_175_COL_OFFSET % 2);
    TEST_ASSERT_EQUAL(0, OWL_CO5300_RES % 2);
}

static void test_rounding_grows_to_even_start_and_odd_end(void)
{
    int32_t x1 = 1, y1 = 3, x2 = 10, y2 = 3;
    owl_co5300_round_area(&x1, &y1, &x2, &y2);
    TEST_ASSERT_EQUAL(0, x1);
    TEST_ASSERT_EQUAL(2, y1);
    TEST_ASSERT_EQUAL(11, x2);
    TEST_ASSERT_EQUAL(3, y2);

    x1 = 0, y1 = 0, x2 = OWL_CO5300_RES - 1, y2 = OWL_CO5300_RES - 1;
    owl_co5300_round_area(&x1, &y1, &x2, &y2);
    TEST_ASSERT_EQUAL(0, x1);
    TEST_ASSERT_EQUAL(OWL_CO5300_RES - 1, x2);
}

static void test_rounding_every_span_stays_in_the_frame(void)
{
    for (int32_t a = 0; a < OWL_CO5300_RES; a++) {
        for (int32_t b = a; b < OWL_CO5300_RES; b++) {
            int32_t x1 = a, y1 = a, x2 = b, y2 = b;
            owl_co5300_round_area(&x1, &y1, &x2, &y2);
            if (x1 % 2 != 0 || x2 % 2 != 1 || x1 > a || x2 < b || x1 < 0 || x2 > OWL_CO5300_RES - 1 ||
                a - x1 > 1 || x2 - b > 1) {
                TEST_FAIL_MESSAGE("a rounded span is misaligned, shrank, grew too much or left the frame");
            }
        }
    }
}

static void test_touch_map_identity_and_clamp(void)
{
    owl_touch_orient_t none = {false, false, false};
    int x = -1, y = -1;
    owl_touch_map(none, OWL_CO5300_RES, 10, 20, &x, &y);
    TEST_ASSERT_EQUAL(10, x);
    TEST_ASSERT_EQUAL(20, y);
    owl_touch_map(none, OWL_CO5300_RES, -3, 500, &x, &y);
    TEST_ASSERT_EQUAL(0, x);
    TEST_ASSERT_EQUAL(465, y);
}

static void test_touch_map_mirrors_then_swaps(void)
{
    int x = -1, y = -1;
    owl_touch_map((owl_touch_orient_t){.mirror_x = true}, OWL_CO5300_RES, 0, 20, &x, &y);
    TEST_ASSERT_EQUAL(465, x);
    TEST_ASSERT_EQUAL(20, y);
    owl_touch_map((owl_touch_orient_t){.mirror_y = true}, OWL_CO5300_RES, 10, 465, &x, &y);
    TEST_ASSERT_EQUAL(10, x);
    TEST_ASSERT_EQUAL(0, y);
    owl_touch_map((owl_touch_orient_t){.swap_xy = true}, OWL_CO5300_RES, 10, 20, &x, &y);
    TEST_ASSERT_EQUAL(20, x);
    TEST_ASSERT_EQUAL(10, y);
    /* The mirror acts on the controller's X before the swap moves it to the frame's Y. */
    owl_touch_map((owl_touch_orient_t){.swap_xy = true, .mirror_x = true}, OWL_CO5300_RES, 10, 20, &x, &y);
    TEST_ASSERT_EQUAL(20, x);
    TEST_ASSERT_EQUAL(455, y);
    /* Waveshare's setting, both mirrors: a corner goes to the opposite corner. */
    owl_touch_map((owl_touch_orient_t){.mirror_x = true, .mirror_y = true}, OWL_CO5300_RES, 0, 465, &x, &y);
    TEST_ASSERT_EQUAL(465, x);
    TEST_ASSERT_EQUAL(0, y);
}

static void test_cst816_point(void)
{
    int x = -1, y = -1;
    /* One finger; the event bits (7:6) of XH and the touch ID (7:4) of YH are not coordinates. */
    const uint8_t down[OWL_CST816_POINT_LEN] = {0x01, 0x81, 0x0A, 0x10, 0xC8};
    TEST_ASSERT_TRUE(owl_cst816_point(down, &x, &y));
    TEST_ASSERT_EQUAL(266, x);
    TEST_ASSERT_EQUAL(200, y);

    const uint8_t up[OWL_CST816_POINT_LEN] = {0x00, 0x41, 0x0A, 0x00, 0xC8};
    x = -1;
    TEST_ASSERT_FALSE(owl_cst816_point(up, &x, &y));
    TEST_ASSERT_EQUAL(-1, x);
}

static void cst9217_frame(uint8_t out[OWL_CST9217_POINT_LEN], uint8_t status, int x, int y, uint8_t count,
                          uint8_t ack)
{
    for (size_t i = 0; i < OWL_CST9217_POINT_LEN; i++) {
        out[i] = 0;
    }
    out[0] = status;
    out[1] = (uint8_t)(x >> 4);
    out[2] = (uint8_t)(y >> 4);
    out[3] = (uint8_t)(((x & 0x0F) << 4) | (y & 0x0F));
    out[5] = count;
    out[6] = ack;
}

static void test_cst9217_point(void)
{
    uint8_t f[OWL_CST9217_POINT_LEN];
    int x = -1, y = -1;
    cst9217_frame(f, 0x06, 300, 200, 1, OWL_CST9217_ACK);
    TEST_ASSERT_TRUE(owl_cst9217_point(f, &x, &y));
    TEST_ASSERT_EQUAL(300, x);
    TEST_ASSERT_EQUAL(200, y);

    cst9217_frame(f, 0x16, 465, 0, 1, OWL_CST9217_ACK); /* finger ID 1 in the high nibble */
    TEST_ASSERT_TRUE(owl_cst9217_point(f, &x, &y));
    TEST_ASSERT_EQUAL(465, x);
    TEST_ASSERT_EQUAL(0, y);

    cst9217_frame(f, 0x06, 300, 200, 1, 0x00); /* no acknowledge: no report */
    TEST_ASSERT_FALSE(owl_cst9217_point(f, &x, &y));
    cst9217_frame(f, 0x06, 300, 200, 0x80, OWL_CST9217_ACK); /* key flag only, no finger */
    TEST_ASSERT_FALSE(owl_cst9217_point(f, &x, &y));
    cst9217_frame(f, 0x00, 300, 200, 1, OWL_CST9217_ACK); /* finger lifted */
    TEST_ASSERT_FALSE(owl_cst9217_point(f, &x, &y));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_command_words_frame_the_command_in_the_middle_bytes);
    RUN_TEST(test_window_shifts_columns_by_the_offset);
    RUN_TEST(test_viewe_table);
    RUN_TEST(test_waveshare_table);
    RUN_TEST(test_offsets_keep_windows_even);
    RUN_TEST(test_rounding_grows_to_even_start_and_odd_end);
    RUN_TEST(test_rounding_every_span_stays_in_the_frame);
    RUN_TEST(test_touch_map_identity_and_clamp);
    RUN_TEST(test_touch_map_mirrors_then_swaps);
    RUN_TEST(test_cst816_point);
    RUN_TEST(test_cst9217_point);
    return UNITY_END();
}
