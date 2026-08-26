#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "framecore/status.h"

namespace framecore {

struct PingFrame {
  uint64_t opaque_data = 0;

  std::vector<uint8_t> EncodePayload() const;
  static Status DecodePayload(const uint8_t* data, size_t len, PingFrame* out);
};

}
