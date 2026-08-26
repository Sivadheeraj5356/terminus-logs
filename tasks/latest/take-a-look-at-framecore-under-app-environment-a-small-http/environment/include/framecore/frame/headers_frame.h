#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "framecore/status.h"

namespace framecore {

struct HeadersFrame {
  std::vector<uint8_t> header_block;

  std::vector<uint8_t> EncodePayload() const;
  static Status DecodePayload(const uint8_t* data, size_t len, HeadersFrame* out);
};

}
