cmake_minimum_required(VERSION 3.20)
project(demo_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_EXTENSIONS OFF)

include("${CMAKE_CURRENT_SOURCE_DIR}/config/build_flags.cmake")

add_executable(demo_engine
  driver/main.cpp
  driver/lab_audit_strings.cpp
  driver/integrator_loop.cpp
  kernels/pair_ops.cpp
  kernels/pair_ops_shadow.cpp
  wrap/tile_wrap.cpp
  vault/segment_store.cpp
  vault/bulk_encoder.cpp
  measure/bulk_reductions.cpp
  codec_lane/journal_codec.cpp
  session_plane/epoch_fold.cpp
)

target_include_directories(demo_engine PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/include")

target_compile_options(demo_engine PRIVATE "${DEMO_ENGINE_WARNING_FLAGS}")
