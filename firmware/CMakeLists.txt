cmake_minimum_required(VERSION 3.22)
# Common defaults first, then the board's. QEMU is the only board until the dev kits arrive (P3).
set(SDKCONFIG_DEFAULTS "sdkconfig.defaults;sdkconfig.qemu")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(owltunes)
