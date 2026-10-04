set(srcs main.c demo_state.c)
if(CONFIG_OWL_BOARD_QEMU)
    list(APPEND srcs board_qemu.c)
endif()

idf_component_register(SRCS ${srcs}
                       INCLUDE_DIRS .
                       REQUIRES owl_core spotify owl_ui esp_lcd esp_timer)
