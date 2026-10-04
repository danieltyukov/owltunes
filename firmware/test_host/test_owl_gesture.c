#include "owl_gesture.h"
#include "test_util.h"
#include "unity.h"

static void test_short_press_without_double_fires_on_release(void)
{
    owl_btn_t b;
    owl_btn_init(&b, false);
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, true, 0));
    TEST_ASSERT_EQUAL(OWL_BTN_SHORT, owl_btn_update(&b, false, 100));
}

static void test_hold_fires_once_then_release(void)
{
    owl_btn_t b;
    owl_btn_init(&b, false);
    owl_btn_update(&b, true, 0);
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, true, 449));
    TEST_ASSERT_EQUAL(OWL_BTN_HOLD, owl_btn_update(&b, true, 450));
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, true, 600));
    TEST_ASSERT_EQUAL(OWL_BTN_HOLD_RELEASE, owl_btn_update(&b, false, 700));
}

static void test_double_press(void)
{
    owl_btn_t b;
    owl_btn_init(&b, true);
    owl_btn_update(&b, true, 0);
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, false, 80));
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, true, 200));
    TEST_ASSERT_EQUAL(OWL_BTN_DOUBLE, owl_btn_update(&b, false, 260));
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, false, 900));
}

static void test_single_press_with_double_enabled_waits_for_window(void)
{
    owl_btn_t b;
    owl_btn_init(&b, true);
    owl_btn_update(&b, true, 0);
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, false, 80));
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, false, 380));
    TEST_ASSERT_EQUAL(OWL_BTN_SHORT, owl_btn_update(&b, false, 381));
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, false, 400));
}

static void test_late_second_press_reports_the_first_as_short(void)
{
    owl_btn_t b;
    owl_btn_init(&b, true);
    owl_btn_update(&b, true, 0);
    owl_btn_update(&b, false, 80);
    TEST_ASSERT_EQUAL(OWL_BTN_SHORT, owl_btn_update(&b, true, 500));
    TEST_ASSERT_EQUAL(OWL_BTN_NONE, owl_btn_update(&b, false, 560));
    TEST_ASSERT_EQUAL(OWL_BTN_SHORT, owl_btn_update(&b, false, 900));
}

static void test_hold_after_tap_wins_over_double(void)
{
    owl_btn_t b;
    owl_btn_init(&b, true);
    owl_btn_update(&b, true, 0);
    owl_btn_update(&b, false, 80);
    owl_btn_update(&b, true, 200);
    TEST_ASSERT_EQUAL(OWL_BTN_HOLD, owl_btn_update(&b, true, 650));
    TEST_ASSERT_EQUAL(OWL_BTN_HOLD_RELEASE, owl_btn_update(&b, false, 700));
}

static void test_ring_counts_steps_and_keeps_fractions(void)
{
    owl_ring_t r;
    owl_ring_init(&r, 24); /* 15 degrees per step */
    TEST_ASSERT_EQUAL_INT32(0, owl_ring_update(&r, 0.0f));
    TEST_ASSERT_EQUAL_INT32(1, owl_ring_update(&r, 16.0f));
    TEST_ASSERT_EQUAL_INT32(0, owl_ring_update(&r, 29.0f));
    TEST_ASSERT_EQUAL_INT32(1, owl_ring_update(&r, 31.0f));
    TEST_ASSERT_EQUAL_INT32(-2, owl_ring_update(&r, 0.0f));
}

static void test_ring_wraps_around_zero(void)
{
    owl_ring_t r;
    owl_ring_init(&r, 24);
    owl_ring_update(&r, 350.0f);
    TEST_ASSERT_EQUAL_INT32(1, owl_ring_update(&r, 5.0f));
    TEST_ASSERT_EQUAL_INT32(-1, owl_ring_update(&r, 350.0f));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_short_press_without_double_fires_on_release);
    RUN_TEST(test_hold_fires_once_then_release);
    RUN_TEST(test_double_press);
    RUN_TEST(test_single_press_with_double_enabled_waits_for_window);
    RUN_TEST(test_late_second_press_reports_the_first_as_short);
    RUN_TEST(test_hold_after_tap_wins_over_double);
    RUN_TEST(test_ring_counts_steps_and_keeps_fractions);
    RUN_TEST(test_ring_wraps_around_zero);
    return UNITY_END();
}
