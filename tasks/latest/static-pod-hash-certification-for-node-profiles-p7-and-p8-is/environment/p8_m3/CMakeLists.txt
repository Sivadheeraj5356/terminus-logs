add_library(p8_m3 STATIC
  src/bind_c.cpp
  src/legacy_scan.cpp
)
target_include_directories(p8_m3 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(p8_m3 PUBLIC k4_w2)
