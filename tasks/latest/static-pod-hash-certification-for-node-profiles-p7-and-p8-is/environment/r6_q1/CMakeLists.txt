add_library(r6_q1 STATIC
  src/fence_d.cpp
)
target_include_directories(r6_q1 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
