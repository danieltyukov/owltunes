# OwlTunes main board rev A. Requirements must not depend on the configuration, so the component is
# always registered and only its source is left out for other boards. The pin map is
# board_owltunes_reva.h here, which tools/hw/hw_pinmap.py checks against the netlist.
set(srcs)
if(CONFIG_OWL_BOARD_OWLTUNES_REVA)
    set(srcs bsp_owltunes_reva.c)
endif()
idf_component_register(SRCS ${srcs}
                       PRIV_INCLUDE_DIRS .
                       REQUIRES bsp owl_ui owl_amoled esp_driver_gpio esp_driver_i2c esp_timer)
