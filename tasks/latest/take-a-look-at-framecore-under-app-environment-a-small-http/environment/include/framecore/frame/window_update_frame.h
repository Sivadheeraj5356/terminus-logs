#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "framecore/status.h"

namespace framecore {

struct WindowUpdateFrame {
  uint32_t window_size_increment = 0;

  std::vector<uint8_t> EncodePayload() const;
  static Status DecodePayload(const uint8_t* data, size_t len, WindowUpdateFrame* out);
};

}
