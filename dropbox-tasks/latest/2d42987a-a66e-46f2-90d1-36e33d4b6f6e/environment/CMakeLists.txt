cmake_minimum_required(VERSION 3.16)
project(wireguard_preshared_rotate CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(wg_run
  include/wg_md5.cpp
  engine/src/wg_run.cpp
  engine/src/wg_snap.cpp
  engine/src/wg_orch.cpp
  engine/src/wg_emit.cpp
  engine/src/wg_replay.cpp
  k7m/src/k7_mux.cpp
  k7m/src/k7_help.cpp
  f3p/src/f3_mux.cpp
  f3p/src/f3_help.cpp
  p5k/src/p5_mux.cpp
  p5k/src/p5_help.cpp
  h9w/src/h9_mux.cpp
  h9w/src/h9_help.cpp
  libs/shared/src/shared_gate.cpp
)

target_include_directories(wg_run PRIVATE include k7m/include f3p/include p5k/include h9w/include)
target_compile_options(wg_run PRIVATE -Wall -Wextra)
