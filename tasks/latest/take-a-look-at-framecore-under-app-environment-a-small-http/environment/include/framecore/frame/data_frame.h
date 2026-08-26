#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "framecore/status.h"

namespace framecore {

struct DataFrame {
  std::vector<uint8_t> payload;

  std::vector<uint8_t> EncodePayload() const;
  static Status DecodePayload(const uint8_t* data, size_t len, DataFrame* out);
};

}
