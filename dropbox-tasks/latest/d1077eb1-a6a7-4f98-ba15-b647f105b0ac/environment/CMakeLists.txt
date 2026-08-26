cmake_minimum_required(VERSION 3.25)
project(windowed_hann_energy_audit LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(hann_energy_audit
  src/main.cpp
  src/io/pack_loader.cpp
  src/metrics/reconstruct.cpp
  src/metrics/window.cpp
  src/metrics/goertzel.cpp
  src/metrics/bins.cpp
  src/metrics/aggregate.cpp
  src/metrics/scale.cpp
  src/util/digest.cpp
)

target_include_directories(hann_energy_audit PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)

install(TARGETS hann_energy_audit RUNTIME DESTINATION bin)
