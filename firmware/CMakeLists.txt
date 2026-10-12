cmake_minimum_required(VERSION 3.22)
# The board: tools/firmware.sh passes -DOWL_BOARD=<board> (QEMU when nothing is passed, so plain
# idf.py runs and CI keep working). The board's sdkconfig.board is layered over the common defaults
# and selects the matching OWL_BOARD Kconfig choice; the BSP components live in boards/.
set(OWL_BOARD "qemu" CACHE STRING "Board to build for: a directory name under boards/ without bsp_")
if(NOT EXISTS "${CMAKE_CURRENT_LIST_DIR}/boards/bsp_${OWL_BOARD}/sdkconfig.board")
    message(FATAL_ERROR "Unknown board '${OWL_BOARD}': boards/bsp_${OWL_BOARD}/sdkconfig.board is missing")
endif()
set(SDKCONFIG_DEFAULTS "sdkconfig.defaults;boards/bsp_${OWL_BOARD}/sdkconfig.board")
set(EXTRA_COMPONENT_DIRS boards)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(owltunes)
if(NOT CONFIG_OWL_BOARD_NAME STREQUAL OWL_BOARD)
    message(FATAL_ERROR "This build's sdkconfig is for '${CONFIG_OWL_BOARD_NAME}', not '${OWL_BOARD}'. "
                        "Delete it (tools/firmware.sh does this when the board's defaults change).")
endif()
