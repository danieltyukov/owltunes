# QEMU's virtual RGB panel. Requirements must not depend on the configuration, so the component is
# always registered and only its source is left out for other boards.
set(srcs)
if(CONFIG_OWL_BOARD_QEMU)
    set(srcs bsp_qemu.c)
endif()
idf_component_register(SRCS ${srcs} REQUIRES bsp owl_ui esp_lcd)
