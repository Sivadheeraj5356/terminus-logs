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
  return k.rfind("q46.", 0) == 0;
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

}  // namespace

UnitPlan fold_r1(const RawItem& in, const BandCtx& ctx) {
  UnitPlan out;
  std::vector<std::string> labels;
  for (const auto& kv : in.labels) {
    labels.push_back(kv.first + "=" + kv.second);
  }
  std::sort(labels.begin(), labels.end());
  (void)ctx;
  (void)annex_key;
  (void)slice_value;
  const std::string stage = "/app/output/stage";
  const fs::path jpath = fs::path(stage) / "journal" / (in.mid + ".frames");
  fs::create_directories(jpath.parent_path());
  out.parent_tip_hex = hex32(fnv1a32(""));
  if (fs::exists(jpath)) {
    std::ifstream jin(jpath);
    std::ostringstream ss;
    ss << jin.rdbuf();
    out.parent_tip_hex = hex32(fnv1a32(ss.str()));
  }
  {
    std::ofstream jout(jpath, std::ios::app);
    jout << "p7|" << join_tokens(labels) << "\n";
  }
  out.slots = labels;
  out.gen = 0;
  return out;
}
