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

std::string tip_chain(const std::string& mid) {
  const std::string stage = slice_value("STAGE_ROOT");
  const fs::path jpath = fs::path(stage) / "journal" / (mid + ".frames");
  if (!fs::exists(jpath)) {
    return hex32(fnv1a32(""));
  }
  std::ifstream in(jpath);
  std::string blob;
  {
    std::ostringstream ss;
    ss << in.rdbuf();
    blob = ss.str();
  }
  std::string concat;
  size_t at = 0;
  while (at < blob.size()) {
    auto nl = blob.find('\n', at);
    if (nl == std::string::npos) {
      break;
    }
    const std::string line = blob.substr(at, nl - at + 1);
    concat += hex32(fnv1a32(line));
    at = nl + 1;
  }
  return hex32(fnv1a32(concat));
}

}  // namespace

RowBundle latch_r3(const ByteDigest& dig, const BandCtx& ctx, const std::string& mid,
                   const UnitPlan& plan) {
  RowBundle row;
  row.mid = mid;
  row.digest_hex = dig.hex;
  row.slot_line = join_slots(plan);
  row.band = ctx.band;
  if (row.band != "p7" && row.band != "p8") {
    row.band = "p7";
  }
  row.cache_epoch = dig.epoch;
  row.journal_tip_hex = tip_chain(mid);
  row.window_id = dig.window_id;
  return row;
}
