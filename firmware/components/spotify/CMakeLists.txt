# Spotify Web API layer: request building and JSON parsing. Transport lives in the firmware.
set(SPOTIFY_SRCS
    src/spotify_request.c
    src/spotify_json.c
    src/spotify_parse_player.c
)

if(ESP_PLATFORM)
    idf_component_register(SRCS ${SPOTIFY_SRCS}
                           INCLUDE_DIRS include
                           PRIV_INCLUDE_DIRS src
                           REQUIRES owl_core)
else()
    add_library(spotify STATIC ${SPOTIFY_SRCS})
    target_include_directories(spotify PUBLIC include PRIVATE src)
    target_link_libraries(spotify PUBLIC owl_core PRIVATE cjson)
endif()
