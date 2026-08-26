cmake_minimum_required(VERSION 3.25)
project(matrix_lto CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
include(${CMAKE_CURRENT_LIST_DIR}/toolchain.cmake)

set(SRC_ROOT /app/environment/src)
set(GEN_ROOT /app/work/gen)
set(OBJ_ROOT /app/work/obj)

file(MAKE_DIRECTORY ${GEN_ROOT} ${OBJ_ROOT})

add_library(matrix_objs OBJECT
  ${SRC_ROOT}/anchor.cpp
  ${SRC_ROOT}/dispatch.cpp
  ${SRC_ROOT}/consumer.cpp
  ${GEN_ROOT}/gate_abi.cpp
  ${SRC_ROOT}/main.cpp
)

target_include_directories(matrix_objs PRIVATE ${SRC_ROOT} ${GEN_ROOT})
set_target_properties(matrix_objs PROPERTIES POSITION_INDEPENDENT_CODE ON)

add_executable(matrix_app $<TARGET_OBJECTS:matrix_objs>)
target_include_directories(matrix_app PRIVATE ${SRC_ROOT} ${GEN_ROOT})
set_target_properties(matrix_app PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY /app/work/bin
  OUTPUT_NAME matrix_app
)
