cmake_minimum_required(VERSION 3.16)
project(sf_model LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(kz_core STATIC
  core/kz/ring.cpp
  core/kz/driver.cpp
  core/kz/legacy_ring.cpp
)
target_include_directories(kz_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/core/kz)

add_library(ep_lane STATIC
  lane/ep/latch.cpp
)
target_include_directories(ep_lane PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/lane/ep)

add_library(nx_lane STATIC
  lane/nx/quota.cpp
  lane/nx/stub_quota.cpp
)
target_include_directories(nx_lane PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/lane/nx)


add_library(sf_bootstrap STATIC
  bootstrap/ring_init.cpp
  bootstrap/latch_init.cpp
  bootstrap/quota_init.cpp
)
target_include_directories(sf_bootstrap PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/core/kz
  ${CMAKE_CURRENT_SOURCE_DIR}/lane/ep
  ${CMAKE_CURRENT_SOURCE_DIR}/lane/nx
)

add_library(libhash STATIC tools/libhash/sha256.cpp)
target_include_directories(libhash PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/tools/libhash)

add_executable(sf_verify
  tools/sf_verify/sf_verify.cpp
  tools/sf_verify/engine.cpp
  tools/sf_verify/pack.cpp
  tools/sf_phases/circ_phase.cpp
  tools/sf_phases/clock_phase.cpp
  tools/sf_phases/burst_phase.cpp
)
target_include_directories(sf_verify PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/tools/sf_verify
  ${CMAKE_CURRENT_SOURCE_DIR}
)
target_link_libraries(sf_verify PRIVATE kz_core ep_lane nx_lane libhash sf_bootstrap)
target_compile_options(sf_verify PRIVATE -Wall -Wextra)

add_executable(evt_pull_stub tools/evt_pull/collector.cpp)
target_compile_definitions(evt_pull_stub PRIVATE COLLECTOR_STUB)
