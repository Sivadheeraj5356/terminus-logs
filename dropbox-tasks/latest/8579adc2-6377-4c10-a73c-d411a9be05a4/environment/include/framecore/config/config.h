#pragma once

#include <cstddef>

namespace framecore {

struct Config {
  size_t max_session_memory = 10 * 1024 * 1024;
  size_t max_header_count = 10000;
  size_t max_concurrent_streams = 100;
  size_t initial_window_size = 65535;
  size_t max_frame_size = 16384;
};

bool IsValidConfig(const Config& config);

}
