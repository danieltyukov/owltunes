# The USB console's developer commands and the JSON status lines the owl answers with. Pure: parsing
# and formatting only, so it builds for the host tests too.
set(OWL_SHELL_SRCS src/owl_shell.c)

if(ESP_PLATFORM)
    idf_component_register(SRCS ${OWL_SHELL_SRCS}
                           INCLUDE_DIRS include
                           REQUIRES owl_core provisioning)
else()
    add_library(owl_shell STATIC ${OWL_SHELL_SRCS})
    target_include_directories(owl_shell PUBLIC include)
    target_link_libraries(owl_shell PUBLIC owl_core provisioning PRIVATE cjson)
endif()
