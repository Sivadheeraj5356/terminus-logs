cmake_minimum_required(VERSION 3.22)
project(sdk_abi_index CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(build_defs/SdkWarnings.cmake)
include(build_defs/SdkToolchain.cmake)

set(SDK_LANE_FILE "${CMAKE_CURRENT_SOURCE_DIR}/profiles/core.lane"
    CACHE FILEPATH "Lane profile consumed by the generator")
set(SDK_LANE_LABEL "core" CACHE STRING "Matrix lane label for probe output")

sdk_add_generator()
sdk_add_shape()
