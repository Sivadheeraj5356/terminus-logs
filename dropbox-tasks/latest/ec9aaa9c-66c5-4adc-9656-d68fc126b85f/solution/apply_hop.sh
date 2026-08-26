#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
cat > k4_w2/src/hop_b.cpp <<'EOF'
#include "raw_io.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <vector>

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

char scope_char(const BandCtx& ctx) {
  if (!ctx.scope_letter.empty()) {
    return ctx.scope_letter[0];
  }
  return 'Q';
}

int resolve_window(const BandCtx& ctx) {
  const auto table = split_csv(slice_value("SEAL_TABLE"));
  int mod = 1;
  try {
    mod = std::stoi(slice_value("WINDOW_MOD"));
  } catch (...) {
    mod = 1;
  }
  if (mod <= 0 || table.empty()) {
    return 0;
  }
  return static_cast<int>(fnv1a32(ctx.set_stem) % static_cast<uint32_t>(mod));
}

std::string seal_for_window(int window_id, int gen) {
  const auto table = split_csv(slice_value("SEAL_TABLE"));
  if (table.empty()) {
    return slice_value("SEAL");
  }
  const size_t idx =
      static_cast<size_t>((window_id + gen) % static_cast<int>(table.size()));
  return table[idx];
}

int load_and_bump_epoch(const std::string& mid, bool annex_on, int window_id) {
  const std::string stage = slice_value("STAGE_ROOT");
  const fs::path cpath = fs::path(stage) / "cache" / (mid + ".kv");
  fs::create_directories(cpath.parent_path());
  int epoch = 1;
  int annex_last = -1;
  int window_last = -1;
  if (fs::exists(cpath)) {
    std::ifstream in(cpath);
    std::string line;
    while (std::getline(in, line)) {
      if (line.rfind("EPOCH=", 0) == 0) {
        epoch = std::stoi(line.substr(6));
      } else if (line.rfind("ANNEX_LAST=", 0) == 0) {
        annex_last = std::stoi(line.substr(11));
      } else if (line.rfind("WINDOW_LAST=", 0) == 0) {
        window_last = std::stoi(line.substr(12));
      }
    }
    const int cur = annex_on ? 1 : 0;
    if ((annex_last >= 0 && annex_last != cur) ||
        (window_last >= 0 && window_last != window_id)) {
      epoch += 1;
    }
  }
  {
    std::ofstream out(cpath);
    out << "ANNEX_LAST=" << (annex_on ? 1 : 0) << "\n";
    out << "WINDOW_LAST=" << window_id << "\n";
    out << "EPOCH=" << epoch << "\n";
  }
  return epoch;
}

}  // namespace

ByteDigest mix_r2(const UnitPlan& plan, const BandCtx& ctx, const std::string& mid) {
  const std::string slot_line = join_slots(plan);
  const int window_id = resolve_window(ctx);
  const std::string seal = seal_for_window(window_id, plan.gen);
  const int epoch = load_and_bump_epoch(mid, ctx.annex_on, window_id);
  const std::string window_s = std::to_string(window_id);
  const std::string parent =
      plan.parent_tip_hex.empty() ? hex32(fnv1a32("")) : plan.parent_tip_hex;
  const std::string wire =
      mid + "|" + slot_line + "|" + std::string(1, scope_char(ctx)) + "|W" + window_s;
  const std::string epoch_s = std::to_string(epoch);
  ByteDigest out;
  out.wire = wire;
  out.hex = hex32(fnv1a32(wire)) + hex32(fnv1a32(slot_line + mid + plan.ns + seal +
                                                   epoch_s + parent + "W" + window_s));
  out.epoch = epoch;
  out.window_id = window_id;
  return out;
}
EOF
