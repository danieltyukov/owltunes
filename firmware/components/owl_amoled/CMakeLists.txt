# The round CO5300 AMOLED and its touch controller, shared by the boards that carry one. The command
# encoding, window maths, init tables and touch decoding are pure and also build for the host tests;
# the driver and LVGL glue build only when an AMOLED board is selected (CONFIG_OWL_AMOLED).
set(OWL_AMOLED_PURE_SRCS src/owl_co5300.c src/owl_touch.c)

if(ESP_PLATFORM)
    set(srcs)
    if(CONFIG_OWL_AMOLED)
        set(srcs ${OWL_AMOLED_PURE_SRCS} src/owl_amoled.c)
    endif()
    idf_component_register(SRCS ${srcs}
                           INCLUDE_DIRS include
                           REQUIRES lvgl__lvgl
                           PRIV_REQUIRES esp_lcd esp_driver_spi esp_driver_i2c esp_driver_gpio esp_timer heap)
else()
    add_library(owl_amoled STATIC ${OWL_AMOLED_PURE_SRCS})
    target_include_directories(owl_amoled PUBLIC include)
endif()
