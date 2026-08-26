#include "raw_io.h"

#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace {

std::string read_all(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    throw std::runtime_error("open fail");
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

std::string extract_string(const std::string& blob, const std::string& key) {
  const std::string needle = "\"" + key + "\"";
  auto pos = blob.find(needle);
  if (pos == std::string::npos) {
    return {};
  }
  pos = blob.find(':', pos);
  if (pos == std::string::npos) {
    return {};
  }
  pos = blob.find('"', pos);
  if (pos == std::string::npos) {
    return {};
  }
  auto end = blob.find('"', pos + 1);
  if (end == std::string::npos) {
    return {};
  }
  return blob.substr(pos + 1, end - pos - 1);
}

std::map<std::string, std::string> extract_map(const std::string& blob,
                                               const std::string& key) {
  std::map<std::string, std::string> out;
  const std::string needle = "\"" + key + "\"";
  auto pos = blob.find(needle);
  if (pos == std::string::npos) {
    return out;
  }
  pos = blob.find('{', pos);
  if (pos == std::string::npos) {
    return out;
  }
  auto depth = 0;
  size_t i = pos;
  for (; i < blob.size(); ++i) {
    if (blob[i] == '{') {
      ++depth;
    } else if (blob[i] == '}') {
      --depth;
      if (depth == 0) {
        break;
      }
    }
  }
  const std::string body = blob.substr(pos + 1, i - pos - 1);
  size_t at = 0;
  while (at < body.size()) {
    auto kstart = body.find('"', at);
    if (kstart == std::string::npos) {
      break;
    }
    auto kend = body.find('"', kstart + 1);
    if (kend == std::string::npos) {
      break;
    }
    auto vstart = body.find('"', body.find(':', kend));
    if (vstart == std::string::npos) {
      break;
    }
    auto vend = body.find('"', vstart + 1);
    if (vend == std::string::npos) {
      break;
    }
    out[body.substr(kstart + 1, kend - kstart - 1)] =
        body.substr(vstart + 1, vend - vstart - 1);
    at = vend + 1;
  }
  return out;
}

bool parse_bool(const std::string& blob, const std::string& key) {
  const std::string needle = key + " = ";
  auto pos = blob.find(needle);
  if (pos == std::string::npos) {
    return false;
  }
  pos += needle.size();
  return blob.compare(pos, 4, "true") == 0;
}

}  // namespace

RawItem load_item_json(const std::string& path) {
  const std::string blob = read_all(path);
  RawItem item;
  item.mid = extract_string(blob, "manifest_id");
  item.name = extract_string(blob, "name");
  item.ns = extract_string(blob, "namespace");
  item.labels = extract_map(blob, "labels");
  item.annots = extract_map(blob, "annotations");
  return item;
}

std::string extract_toml_string(const std::string& blob, const std::string& key) {
  const std::string needle = key + " = \"";
  auto pos = blob.find(needle);
  if (pos == std::string::npos) {
    return {};
  }
  pos += needle.size();
  auto end = blob.find('"', pos);
  if (end == std::string::npos) {
    return {};
  }
  return blob.substr(pos, end - pos);
}

BandCtx load_band_ctx(const std::string& profile_path) {
  const std::string blob = read_all(profile_path);
  BandCtx ctx;
  ctx.band = extract_toml_string(blob, "band");
  ctx.annex_on = parse_bool(blob, "annex_keys");
  ctx.scope_letter = extract_toml_string(blob, "scope_letter");
  return ctx;
}
