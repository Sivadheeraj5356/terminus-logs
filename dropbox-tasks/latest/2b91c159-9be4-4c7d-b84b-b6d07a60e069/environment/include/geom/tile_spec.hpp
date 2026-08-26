#pragma once

#include "engine/types.hpp"

struct TileSpec {
  double span{12.8};
};

struct WrapDelta {
  double3 shift{};
  uint32_t crossings_added{0};
};
