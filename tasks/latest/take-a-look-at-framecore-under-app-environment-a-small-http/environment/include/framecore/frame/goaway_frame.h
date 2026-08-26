#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "framecore/status.h"

namespace framecore {

struct GoawayFrame {
  uint32_t last_stream_id = 0;
  uint32_t error_code = 0;
  std::vector<uint8_t> debug_data;

  std::vector<uint8_t> EncodePayload() const;
  static Status DecodePayload(const uint8_t* data, size_t len, GoawayFrame* out);
};

}
