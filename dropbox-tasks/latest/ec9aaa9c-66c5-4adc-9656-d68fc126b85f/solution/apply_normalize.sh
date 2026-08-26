#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
cat > k4_w2/src/normalize_a.cpp <<'EOF'
#include "raw_io.h"

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>

namespace fs = std::filesystem;

namespace {

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

bool annex_key(const std::string& k) {
  const std::string prefix = slice_value("ANNEX_PREFIX");
  if (prefix.empty()) {
    return false;
  }
  return k.rfind(prefix, 0) == 0;
}

std::string join_tokens(const std::vector<std::string>& toks) {
  std::ostringstream oss;
  for (size_t i = 0; i < toks.size(); ++i) {
    if (i) {
      oss << ',';
    }
    oss << toks[i];
  }
  return oss.str();
}

std::string tip_chain_blob(const std::string& blob) {
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

int count_complete_lines(const fs::path& jpath) {
  if (!fs::exists(jpath)) {
    return 0;
  }
  std::ifstream jin(jpath);
  std::string line;
  int prior = 0;
  while (std::getline(jin, line)) {
    ++prior;
  }
  return prior;
}

std::string parent_tip_of(const fs::path& jpath) {
  if (!fs::exists(jpath)) {
    return hex32(fnv1a32(""));
  }
  std::ifstream jin(jpath);
  std::ostringstream ss;
  ss << jin.rdbuf();
  return tip_chain_blob(ss.str());
}

}  // namespace

UnitPlan fold_r1(const RawItem& in, const BandCtx& ctx) {
  UnitPlan out;
  std::vector<std::string> annex;
  std::vector<std::string> labels;
  if (ctx.annex_on) {
    for (const auto& kv : in.annots) {
      if (annex_key(kv.first)) {
        annex.push_back(kv.first + "=" + kv.second);
      }
    }
    std::sort(annex.begin(), annex.end());
  }
  for (const auto& kv : in.labels) {
    labels.push_back(kv.first + "=" + kv.second);
  }
  std::sort(labels.begin(), labels.end());
  const std::string order = slice_value("ORDER");
  std::vector<std::string> base;
  if (order == "annex_before_labels") {
    base.insert(base.end(), annex.begin(), annex.end());
    base.insert(base.end(), labels.begin(), labels.end());
  } else {
    base.insert(base.end(), labels.begin(), labels.end());
    base.insert(base.end(), annex.begin(), annex.end());
  }
  const std::string stage = slice_value("STAGE_ROOT");
  const fs::path jpath = fs::path(stage) / "journal" / (in.mid + ".frames");
  fs::create_directories(jpath.parent_path());
  out.parent_tip_hex = parent_tip_of(jpath);
  const int rev = count_complete_lines(jpath) + 1;
  const std::string body = join_tokens(base);
  {
    std::ofstream jout(jpath, std::ios::app);
    jout << "GEN=" << rev << "|BAND=" << ctx.band << "|BODY=" << body << "\n";
  }
  out.slots = base;
  out.slots.push_back("rev=" + std::to_string(rev));
  out.gen = rev;
  out.ns = in.ns;
  return out;
}
EOF
