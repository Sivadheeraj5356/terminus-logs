#pragma once

#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

#include "framecore/status.h"

namespace framecore {

struct SettingsFrame {
  std::vector<std::pair<uint16_t, uint32_t>> entries;

  std::vector<uint8_t> EncodePayload() const;
  static Status DecodePayload(const uint8_t* data, size_t len, SettingsFrame* out);
};

}
