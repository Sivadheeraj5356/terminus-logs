#include "bind_types.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>

namespace fs = std::filesystem;

namespace {

std::string join_slots(const UnitPlan& plan) {
  std::ostringstream oss;
  for (size_t i = 0; i < plan.slots.size(); ++i) {
    if (i) {
      oss << ',';
    }
    oss << plan.slots[i];
  }
  return oss.str();
}

uint32_t fnv1a32(const std::string& s) {
  uint32_t h = 2166136261u;
  for (unsigned char c : s) {
    h ^= c;
    h *= 16777619u;
  }
  return h;
}

std::string hex32(uint32_t v) {
  static const char* k = "0123456789abcdef";
  std::string out(8, '0');
  for (int i = 7; i >= 0; --i) {
    out[static_cast<size_t>(i)] = k[v & 0xf];
    v >>= 4;
  }
  return out;
}

std::string tip_raw_file(const std::string& mid) {
  const fs::path jpath = fs::path("/app/output/stage/journal") / (mid + ".frames");
  if (!fs::exists(jpath)) {
    return hex32(fnv1a32(""));
  }
  std::ifstream in(jpath);
  std::ostringstream ss;
  ss << in.rdbuf();
  return hex32(fnv1a32(ss.str()));
}

}  // namespace

RowBundle latch_r3(const ByteDigest& dig, const BandCtx& ctx, const std::string& mid,
                   const UnitPlan& plan) {
  RowBundle row;
  row.mid = mid;
  row.digest_hex = dig.hex.empty() ? dig.wire : dig.hex;
  row.slot_line = join_slots(plan);
  row.band = "p7";
  row.cache_epoch = dig.epoch;
  row.journal_tip_hex = tip_raw_file(mid);
  row.window_id = dig.window_id;
  (void)ctx;
  return row;
}
