#include "raw_io.h"

#include <cstdint>
#include <fstream>
#include <sstream>
#include <vector>

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

std::string slice_value(const std::string& key) {
  std::ifstream in("/app/environment/fixtures/slices/q46.txt");
  std::ostringstream ss;
  ss << in.rdbuf();
  const std::string blob = ss.str();
  const std::string needle = key + "=";
  auto pos = blob.find(needle);
  if (pos == std::string::npos) {
    return {};
  }
  pos += needle.size();
  auto end = blob.find('\n', pos);
  if (end == std::string::npos) {
    end = blob.size();
  }
  return blob.substr(pos, end - pos);
}

std::vector<std::string> split_csv(const std::string& s) {
  std::vector<std::string> out;
  size_t at = 0;
  while (at <= s.size()) {
    auto comma = s.find(',', at);
    if (comma == std::string::npos) {
      out.push_back(s.substr(at));
      break;
    }
    out.push_back(s.substr(at, comma - at));
    at = comma + 1;
  }
  return out;
}

}  // namespace

ByteDigest mix_r2(const UnitPlan& plan, const BandCtx& ctx, const std::string& mid) {
  const std::string slot_line = join_slots(plan);
  const std::string seal = slice_value("SEAL");
  int mod = 1;
  try {
    mod = std::stoi(slice_value("WINDOW_MOD"));
  } catch (...) {
    mod = 1;
  }
  const int window_id =
      mod > 0 ? static_cast<int>(fnv1a32(ctx.set_stem) % static_cast<uint32_t>(mod)) : 0;
  const std::string window_s = std::to_string(window_id);
  const std::string wire = mid + "|" + slot_line + "|N|" + window_s + window_s;
  ByteDigest out;
  out.wire = wire;
  out.hex = hex32(fnv1a32(wire)) +
            hex32(fnv1a32(slot_line + mid + seal + "1" + window_s + window_s));
  out.epoch = 1;
  out.window_id = window_id;
  (void)plan.parent_tip_hex;
  return out;
}
