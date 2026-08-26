#include "framecore/config/config.h"

namespace framecore {

bool IsValidConfig(const Config& config) {
  return config.max_session_memory > 0 && config.max_header_count > 0 &&
         config.max_concurrent_streams > 0 && config.initial_window_size > 0 &&
         config.max_frame_size > 0;
}

}
