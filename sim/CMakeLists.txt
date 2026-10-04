cmake_minimum_required(VERSION 3.22)
project(owltunes_sim C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
option(OWL_SIM_SDL "Build the interactive SDL2 window" OFF)

include(${CMAKE_CURRENT_LIST_DIR}/../cmake/owl_deps.cmake)
owl_fetch_lvgl(${CMAKE_CURRENT_LIST_DIR}/lv_conf.h ${OWL_SIM_SDL})
owl_fetch_cjson()
owl_fetch_stb()
if(OWL_SIM_SDL)
    target_compile_definitions(lvgl PUBLIC OWL_SIM_SDL=1)
endif()

set(OWL_COMPONENTS ${CMAKE_CURRENT_LIST_DIR}/../firmware/components)
add_subdirectory(${OWL_COMPONENTS}/owl_core ${CMAKE_BINARY_DIR}/owl_core)
add_subdirectory(${OWL_COMPONENTS}/spotify ${CMAKE_BINARY_DIR}/spotify)
add_subdirectory(${OWL_COMPONENTS}/owl_ui ${CMAKE_BINARY_DIR}/owl_ui)
owl_strict_warnings(owl_core)
owl_strict_warnings(spotify)
owl_strict_warnings(owl_ui)

set(SIM_SRCS src/main.c src/sim_display.c src/sim_png.c src/sim_art.c src/sim_scenarios.c)
if(OWL_SIM_SDL)
    list(APPEND SIM_SRCS src/sim_sdl.c)
endif()
add_executable(owl_sim ${SIM_SRCS})
target_link_libraries(owl_sim PRIVATE owl_ui spotify owl_core lvgl cjson stb m)
target_compile_definitions(owl_sim PRIVATE OWL_FIXTURE_DIR="${OWL_COMPONENTS}/spotify/test/fixtures")

enable_testing()
# Keep in the same order as SCENARIOS in src/sim_scenarios.c; the scenario_list test enforces it.
set(OWL_SIM_SCENARIOS
    no_device now_playing now_playing_unicode now_playing_volume offline ad_break
    library playlists devices loading presets_wheel presets_screen)
string(REPLACE ";" "," OWL_SIM_SCENARIO_ARG "${OWL_SIM_SCENARIOS}")
add_test(NAME scenario_list COMMAND owl_sim verify-list "${OWL_SIM_SCENARIO_ARG}")
foreach(scenario ${OWL_SIM_SCENARIOS})
    add_test(NAME golden_${scenario}
             COMMAND owl_sim check ${scenario} ${CMAKE_CURRENT_LIST_DIR}/golden ${CMAKE_BINARY_DIR}/out)
endforeach()
