#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "framecore/status.h"

namespace framecore {

struct RstStreamFrame {
  uint32_t error_code = 0;

  std::vector<uint8_t> EncodePayload() const;
  static Status DecodePayload(const uint8_t* data, size_t len, RstStreamFrame* out);
};

}
