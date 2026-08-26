add_executable(spw_run
  src/main.cpp
  src/engine.cpp
  src/pipe_ab.cpp
)
target_include_directories(spw_run PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(spw_run PRIVATE p8_m3 k4_w2 r6_q1)
set_target_properties(spw_run PROPERTIES OUTPUT_NAME spw_run RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
