# LVGL view of the app and player state. Pure presentation: no Spotify or hardware access.
set(OWL_UI_SRCS
    src/owl_ui.c
    src/owl_ui_widgets.c
    src/owl_eyes.c
    src/page_now_playing.c
    src/page_list.c
    src/page_presets.c
    fonts/owl_font_14.c
    fonts/owl_font_20.c
    fonts/owl_font_28.c)

if(ESP_PLATFORM)
    idf_component_register(SRCS ${OWL_UI_SRCS}
                           INCLUDE_DIRS include
                           PRIV_INCLUDE_DIRS src
                           REQUIRES owl_core lvgl__lvgl)
else()
    add_library(owl_ui STATIC ${OWL_UI_SRCS})
    target_include_directories(owl_ui PUBLIC include PRIVATE src)
    target_link_libraries(owl_ui PUBLIC owl_core lvgl)
endif()
