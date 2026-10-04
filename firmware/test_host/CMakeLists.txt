cmake_minimum_required(VERSION 3.22)
project(owltunes_host_tests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
# Catch memory errors in the parsers and the core logic.
add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
add_link_options(-fsanitize=address,undefined)

include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/owl_deps.cmake)
owl_fetch_unity()
owl_fetch_cjson()

set(OWL_COMPONENTS ${CMAKE_CURRENT_LIST_DIR}/../components)
add_subdirectory(${OWL_COMPONENTS}/owl_core ${CMAKE_BINARY_DIR}/owl_core)
owl_strict_warnings(owl_core)

enable_testing()

function(owl_add_test name)
    add_executable(${name} ${name}.c test_util.c)
    target_link_libraries(${name} PRIVATE unity ${ARGN})
    target_compile_definitions(${name} PRIVATE OWL_FIXTURE_DIR="${OWL_COMPONENTS}/spotify/test/fixtures")
    owl_strict_warnings(${name})
    add_test(NAME ${name} COMMAND ${name})
endfunction()

owl_add_test(test_owl_text owl_core)
owl_add_test(test_owl_model owl_core)
owl_add_test(test_owl_cmd owl_core)
owl_add_test(test_owl_poll owl_core)
owl_add_test(test_owl_gesture owl_core)
