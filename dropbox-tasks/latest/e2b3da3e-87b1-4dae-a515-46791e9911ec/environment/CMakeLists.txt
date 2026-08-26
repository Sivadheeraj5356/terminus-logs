cmake_minimum_required(VERSION 3.16)
project(lockctl LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(lockctl
    src/main.cpp
    src/cli.cpp
    src/storage_curve.cpp
    src/flow_laws.cpp
    src/engine.cpp
)

target_include_directories(lockctl PRIVATE include)
