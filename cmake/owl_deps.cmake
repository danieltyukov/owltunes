# Pinned third-party dependencies for host builds (unit tests and the simulator).
# The firmware gets the same libraries from the ESP-IDF component registry.
# SYSTEM keeps warnings from third-party headers out of our -Werror builds.
include(FetchContent)

set(OWL_LVGL_TAG v9.6.0)
set(OWL_UNITY_TAG v2.7.0)
set(OWL_CJSON_TAG v1.7.19)
set(OWL_STB_COMMIT 2c980bb59875b0d32144a71867fbdebb2f77cd20)

function(owl_strict_warnings target)
    target_compile_options(${target} PRIVATE -Wall -Wextra -Werror -Wshadow -Wstrict-prototypes)
endfunction()

macro(owl_fetch_unity)
    if(NOT TARGET unity)
        FetchContent_Declare(unity
            GIT_REPOSITORY https://github.com/ThrowTheSwitch/Unity.git
            GIT_TAG ${OWL_UNITY_TAG}
            GIT_SHALLOW TRUE
            SYSTEM)
        FetchContent_MakeAvailable(unity)
    endif()
endmacro()

macro(owl_fetch_cjson)
    if(NOT TARGET cjson)
        # SOURCE_SUBDIR names a directory without a CMakeLists.txt, so only the sources are fetched.
        FetchContent_Declare(cjson_src
            GIT_REPOSITORY https://github.com/DaveGamble/cJSON.git
            GIT_TAG ${OWL_CJSON_TAG}
            GIT_SHALLOW TRUE
            SOURCE_SUBDIR owl-sources-only)
        FetchContent_MakeAvailable(cjson_src)
        add_library(cjson STATIC ${cjson_src_SOURCE_DIR}/cJSON.c)
        target_include_directories(cjson SYSTEM PUBLIC ${cjson_src_SOURCE_DIR})
    endif()
endmacro()

macro(owl_fetch_stb)
    if(NOT TARGET stb)
        FetchContent_Declare(stb_src
            URL https://github.com/nothings/stb/archive/${OWL_STB_COMMIT}.tar.gz
            SOURCE_SUBDIR owl-sources-only)
        FetchContent_MakeAvailable(stb_src)
        add_library(stb INTERFACE)
        target_include_directories(stb SYSTEM INTERFACE ${stb_src_SOURCE_DIR})
    endif()
endmacro()

# conf: absolute path of the lv_conf.h to build with. sdl: ON to build LVGL's SDL2 driver.
macro(owl_fetch_lvgl conf sdl)
    if(NOT TARGET lvgl)
        set(LV_BUILD_CONF_PATH ${conf} CACHE PATH "" FORCE)
        set(CONFIG_LV_BUILD_DEMOS OFF CACHE BOOL "" FORCE)
        set(CONFIG_LV_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
        set(CONFIG_LV_USE_THORVG OFF CACHE BOOL "" FORCE)
        set(CONFIG_LV_USE_THORVG_INTERNAL OFF CACHE BOOL "" FORCE)
        set(CONFIG_LV_USE_SDL ${sdl} CACHE BOOL "" FORCE)
        set(LV_FETCH_DEPENDENCIES OFF CACHE BOOL "" FORCE)
        set(LV_BUILD_INSTALL OFF CACHE BOOL "" FORCE)
        FetchContent_Declare(lvgl
            GIT_REPOSITORY https://github.com/lvgl/lvgl.git
            GIT_TAG ${OWL_LVGL_TAG}
            GIT_SHALLOW TRUE
            SYSTEM)
        FetchContent_MakeAvailable(lvgl)
    endif()
endmacro()
