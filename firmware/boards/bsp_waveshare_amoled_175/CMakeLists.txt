# Waveshare ESP32-S3-Touch-AMOLED-1.75. Requirements must not depend on the configuration, so the
# component is always registered and only its source is left out for other boards.
set(srcs)
if(CONFIG_OWL_BOARD_WAVESHARE_AMOLED_175)
    set(srcs bsp_waveshare_amoled_175.c)
endif()
idf_component_register(SRCS ${srcs} REQUIRES bsp owl_ui owl_amoled esp_driver_gpio esp_driver_i2c esp_timer)
