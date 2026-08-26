#include "mend_types.h"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

bool parse_gen(const std::string& line, int* gen_out) {
  if (line.rfind("GEN=", 0) != 0) {
    return false;
  }
  auto bar = line.find('|');
  if (bar == std::string::npos) {
    return false;
  }
  try {
    *gen_out = std::stoi(line.substr(4, bar - 4));
  } catch (...) {
    return false;
  }
  return line.find("|BAND=") != std::string::npos && line.find("|BODY=") != std::string::npos;
}

int mend_one(const fs::path& path) {
  if (!fs::exists(path)) {
    return 0;
  }
  std::ifstream in(path);
  std::ostringstream ss;
  ss << in.rdbuf();
  std::string blob = ss.str();
  const int before = static_cast<int>(blob.size());
  if (!blob.empty() && blob.back() != '\n') {
    auto nl = blob.find_last_of('\n');
    if (nl == std::string::npos) {
      blob.clear();
    } else {
      blob.resize(nl + 1);
    }
  }
  std::string kept;
  int expect = 1;
  size_t at = 0;
  while (at < blob.size()) {
    auto nl = blob.find('\n', at);
    if (nl == std::string::npos) {
      break;
    }
    const std::string line = blob.substr(at, nl - at);
    int gen = -1;
    if (!parse_gen(line, &gen) || gen != expect) {
      break;
    }
    kept.append(line);
    kept.push_back('\n');
    ++expect;
    at = nl + 1;
  }
  {
    std::ofstream out(path, std::ios::trunc);
    out << kept;
  }
  return before - static_cast<int>(kept.size());
}

}  // namespace

int mend_r4(const std::string& stage_root) {
  const fs::path journal = fs::path(stage_root) / "journal";
  if (!fs::exists(journal)) {
    return 0;
  }
  int removed = 0;
  for (const auto& entry : fs::directory_iterator(journal)) {
    if (entry.path().extension() == ".frames") {
      removed += mend_one(entry.path());
    }
  }
  return removed;
}
