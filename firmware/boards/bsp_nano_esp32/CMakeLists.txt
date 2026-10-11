# Arduino Nano ESP32. Requirements must not depend on the configuration, so the component is always
# registered and only its source is left out for other boards.
set(srcs)
if(CONFIG_OWL_BOARD_NANO_ESP32)
    set(srcs bsp_nano_esp32.c)
endif()
idf_component_register(SRCS ${srcs} REQUIRES bsp owl_ui heap)
