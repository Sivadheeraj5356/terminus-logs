cmake_minimum_required(VERSION 3.25)
project(spw_workspace LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_subdirectory(k4_w2)
add_subdirectory(p8_m3)
add_subdirectory(r6_q1)
add_subdirectory(tools/q5_driver)
