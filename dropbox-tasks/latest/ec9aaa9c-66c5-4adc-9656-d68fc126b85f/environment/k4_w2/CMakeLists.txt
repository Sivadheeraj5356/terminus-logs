add_library(k4_w2 STATIC
  src/normalize_a.cpp
  src/hop_b.cpp
  src/stub_probe.cpp
  ${CMAKE_SOURCE_DIR}/support/raw_io.cpp
)
target_include_directories(k4_w2 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
