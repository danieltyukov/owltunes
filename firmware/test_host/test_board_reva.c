#include "board_owltunes_reva.h"
#include "test_util.h"
#include "unity.h"

#define N_ELEMS(a) (sizeof(a) / sizeof((a)[0]))

static const int all_pins[] = {
    OWL_PIN_LCD_CS,   OWL_PIN_LCD_CLK,   OWL_PIN_LCD_D0,    OWL_PIN_LCD_D1,      OWL_PIN_LCD_D2,
    OWL_PIN_LCD_D3,   OWL_PIN_LCD_TE,    OWL_PIN_LCD_RST,   OWL_PIN_DISP_EN,     OWL_PIN_TP_SDA,
    OWL_PIN_TP_SCL,   OWL_PIN_TP_INT,    OWL_PIN_TP_RST,    OWL_PIN_I2C_SDA,     OWL_PIN_I2C_SCL,
    OWL_PIN_DOCK_DET, OWL_PIN_BTN_EAR_L, OWL_PIN_BTN_EAR_R, OWL_PIN_BTN_BEAK,    OWL_PIN_HALL_INT,
    OWL_PIN_IMU_INT1, OWL_PIN_CHG_PGOOD, OWL_PIN_CHG_STAT,  OWL_PIN_CHG_SUSPEND, OWL_PIN_EXP_A,
    OWL_PIN_EXP_B,    OWL_PIN_BOOT,      OWL_PIN_XTAL32_P,  OWL_PIN_XTAL32_N,    OWL_PIN_USB_DM,
    OWL_PIN_USB_DP,   OWL_PIN_U0TXD,     OWL_PIN_U0RXD,
};

static void test_pins_are_unique_and_exist_on_the_module(void)
{
    for (size_t i = 0; i < N_ELEMS(all_pins); i++) {
        int p = all_pins[i];
        TEST_ASSERT_TRUE_MESSAGE((p >= 0 && p <= 21) || (p >= 35 && p <= 48), "not a WROOM-1 GPIO");
        TEST_ASSERT_FALSE_MESSAGE(p >= 35 && p <= 37, "GPIO35 to 37 belong to the octal PSRAM");
        for (size_t j = i + 1; j < N_ELEMS(all_pins); j++) {
            TEST_ASSERT_NOT_EQUAL(p, all_pins[j]);
        }
    }
}

static void test_wake_pins(void)
{
    for (int p = 0; p < 64; p++) {
        if (OWL_WAKE_PINS_MASK & (1ULL << p)) {
            TEST_ASSERT_TRUE_MESSAGE(p <= 21, "ext1 wake needs an RTC GPIO (0 to 21)");
        }
    }
    TEST_ASSERT_EQUAL(7, __builtin_popcountll(OWL_WAKE_PINS_MASK));
    TEST_ASSERT_EQUAL_HEX64((1ULL << OWL_PIN_DOCK_DET) | (1ULL << OWL_PIN_BTN_EAR_L) |
                                (1ULL << OWL_PIN_BTN_EAR_R) | (1ULL << OWL_PIN_BTN_BEAK) |
                                (1ULL << OWL_PIN_HALL_INT) | (1ULL << OWL_PIN_IMU_INT1) |
                                (1ULL << OWL_PIN_CHG_PGOOD),
                            OWL_WAKE_PINS_MASK);
    TEST_ASSERT_TRUE(OWL_PIN_DOCK_DET >= 1 && OWL_PIN_DOCK_DET <= 10); /* ADC1, usable with Wi-Fi on */
}

static void test_strap_pins(void)
{
    TEST_ASSERT_EQUAL(0, OWL_PIN_BOOT);
    /* GPIO45 and GPIO46 are only used as outputs that idle low with a pull-down. */
    TEST_ASSERT_EQUAL(45, OWL_PIN_CHG_SUSPEND);
    TEST_ASSERT_EQUAL(46, OWL_PIN_DISP_EN);
    for (size_t i = 0; i < N_ELEMS(all_pins); i++) {
        int p = all_pins[i];
        if (p == 45 || p == 46) {
            TEST_ASSERT_TRUE(p == OWL_PIN_CHG_SUSPEND || p == OWL_PIN_DISP_EN);
        }
    }
}

static void test_display_uses_the_fspi_iomux_pins(void)
{
    TEST_ASSERT_EQUAL(10, OWL_PIN_LCD_CS);
    TEST_ASSERT_EQUAL(12, OWL_PIN_LCD_CLK);
    TEST_ASSERT_EQUAL(11, OWL_PIN_LCD_D0);
    TEST_ASSERT_EQUAL(13, OWL_PIN_LCD_D1);
    TEST_ASSERT_EQUAL(14, OWL_PIN_LCD_D2);
    TEST_ASSERT_EQUAL(9, OWL_PIN_LCD_D3);
}

static void test_sensor_bus_addresses_are_unique(void)
{
    const int addr[] = {OWL_I2C_ADDR_TMAG5273, OWL_I2C_ADDR_MAX17048, OWL_I2C_ADDR_LIS2DW12,
                        OWL_I2C_ADDR_OPT3001, OWL_I2C_ADDR_DRV2605L};
    for (size_t i = 0; i < N_ELEMS(addr); i++) {
        for (size_t j = i + 1; j < N_ELEMS(addr); j++) {
            TEST_ASSERT_NOT_EQUAL(addr[i], addr[j]);
        }
    }
    TEST_ASSERT_EQUAL(0x15, OWL_I2C_ADDR_CST820);
    for (size_t i = 0; i < N_ELEMS(addr); i++) {
        TEST_ASSERT_NOT_EQUAL(addr[i], OWL_I2C_ADDR_CST820);
    }
    TEST_ASSERT_NOT_EQUAL(OWL_PIN_I2C_SDA, OWL_PIN_TP_SDA);
}

static void test_display_bus_clock_is_within_the_panel_limit(void)
{
    TEST_ASSERT_TRUE(OWL_LCD_QSPI_HZ <= OWL_LCD_QSPI_MAX_HZ);
    TEST_ASSERT_EQUAL(0, 80000000 % OWL_LCD_QSPI_HZ);
}

static void test_docked_reading_falls_in_the_perch_window(void)
{
    long series = OWL_DOCK_SERIES_OHM + OWL_PERCH_ID_OHM;
    long mv = 3300L * series / (OWL_DOCK_PULLUP_OHM + series);
    TEST_ASSERT_TRUE(mv > OWL_DOCK_MV_SHORT_MAX && mv < OWL_DOCK_MV_PERCH_MAX);
    long shorted = 3300L * OWL_DOCK_SERIES_OHM / (OWL_DOCK_PULLUP_OHM + OWL_DOCK_SERIES_OHM);
    TEST_ASSERT_TRUE(shorted < OWL_DOCK_MV_SHORT_MAX);
    TEST_ASSERT_TRUE(OWL_DOCK_MV_OPEN_MIN < 3300);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_pins_are_unique_and_exist_on_the_module);
    RUN_TEST(test_wake_pins);
    RUN_TEST(test_strap_pins);
    RUN_TEST(test_display_uses_the_fspi_iomux_pins);
    RUN_TEST(test_sensor_bus_addresses_are_unique);
    RUN_TEST(test_display_bus_clock_is_within_the_panel_limit);
    RUN_TEST(test_docked_reading_falls_in_the_perch_window);
    return UNITY_END();
}
