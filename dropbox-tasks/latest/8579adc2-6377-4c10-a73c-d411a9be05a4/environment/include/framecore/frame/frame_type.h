#pragma once

#include <cstdint>

namespace framecore {

enum class FrameType : uint8_t {
  kData = 0,
  kHeaders = 1,
  kSettings = 2,
  kRstStream = 3,
  kGoaway = 4,
  kPing = 5,
  kWindowUpdate = 6,
};

constexpr uint8_t kFlagEndStream = 0x1;
constexpr uint8_t kFlagEndHeaders = 0x4;
constexpr uint8_t kFlagAck = 0x1;

}
