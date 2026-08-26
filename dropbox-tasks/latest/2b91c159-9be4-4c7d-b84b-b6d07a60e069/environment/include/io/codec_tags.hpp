#pragma once

#include <cstdint>

struct SegmentHeader {
  uint32_t magic{0xa17c3e10};
  uint64_t step_base{0};
};

struct MutableSegmentBody {
  uint64_t stored_crossings{0};
  uint64_t stored_ledger{0};
  bool dirty{false};
};

enum class StoreResult : int { kOk = 0, kBadMagic = 1 };
