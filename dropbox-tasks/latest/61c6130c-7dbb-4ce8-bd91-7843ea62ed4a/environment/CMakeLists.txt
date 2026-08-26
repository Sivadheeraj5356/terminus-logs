cmake_minimum_required(VERSION 3.25)
project(r01_moderation_score LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(r01_score
    r01/source/main.cpp
    r01/source/n1.cpp
    r02/source/n2.cpp
    r03/source/n3.cpp
    r04/source/n4.cpp
    r05/source/n5.cpp
    r01/source/z1.cpp
    r01/source/z2.cpp
    r01/source/z3.cpp
)

target_include_directories(r01_score PRIVATE r01/include)
