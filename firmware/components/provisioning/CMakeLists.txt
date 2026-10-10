# The @owl setup protocol shared by the console and Bluetooth, and the persisted settings model.
set(PROVISIONING_SRCS
    src/owl_prov.c
    src/owl_line.c)

if(ESP_PLATFORM)
    idf_component_register(SRCS ${PROVISIONING_SRCS}
                           INCLUDE_DIRS include
                           REQUIRES owl_core spotify)
else()
    add_library(provisioning STATIC ${PROVISIONING_SRCS})
    target_include_directories(provisioning PUBLIC include)
    target_link_libraries(provisioning PUBLIC owl_core spotify PRIVATE cjson)
endif()
