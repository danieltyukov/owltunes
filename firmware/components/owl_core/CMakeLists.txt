# Pure logic shared by the firmware, the host tests and the simulator. No I/O.
set(OWL_CORE_SRCS
    src/owl_text.c)

if(ESP_PLATFORM)
    idf_component_register(SRCS ${OWL_CORE_SRCS} INCLUDE_DIRS include)
else()
    add_library(owl_core STATIC ${OWL_CORE_SRCS})
    target_include_directories(owl_core PUBLIC include)
endif()
