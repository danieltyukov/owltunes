# The interface every board support package implements. Header only: each board has its own
# bsp_<board> component next to this one, compiled only when the OWL_BOARD choice selects it.
idf_component_register(INCLUDE_DIRS include REQUIRES lvgl__lvgl)
