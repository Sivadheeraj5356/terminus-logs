#include "raw_io.h"

#include <cctype>
#include <cstdint>
#include <fstream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

std::string read_all(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    throw std::runtime_error("open fail");
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

void append_utf8(std::string* out, uint32_t cp) {
  if (cp <= 0x7f) {
    out->push_back(static_cast<char>(cp));
  } else if (cp <= 0x7ff) {
    out->push_back(static_cast<char>(0xc0 | (cp >> 6)));
    out->push_back(static_cast<char>(0x80 | (cp & 0x3f)));
  } else if (cp <= 0xffff) {
    out->push_back(static_cast<char>(0xe0 | (cp >> 12)));
    out->push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3f)));
    out->push_back(static_cast<char>(0x80 | (cp & 0x3f)));
  } else {
    out->push_back(static_cast<char>(0xf0 | (cp >> 18)));
    out->push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3f)));
    out->push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3f)));
    out->push_back(static_cast<char>(0x80 | (cp & 0x3f)));
  }
}

class Json {
 public:
  explicit Json(const std::string& text) : text_(text) {}

  RawItem parse_item() {
    RawItem item;
    expect('{');
    skip_ws();
    if (take('}')) {
      return item;
    }
    while (true) {
      const std::string key = parse_string();
      expect(':');
      if (key == "manifest_id") {
        item.mid = parse_string();
      } else if (key == "name") {
        item.name = parse_string();
      } else if (key == "namespace") {
        item.ns = parse_string();
      } else if (key == "labels") {
        item.labels = parse_string_map();
      } else if (key == "annotations") {
        item.annots = parse_string_map();
      } else {
        skip_value();
      }
      skip_ws();
      if (take('}')) {
        break;
      }
      expect(',');
    }
    return item;
  }

 private:
  void skip_ws() {
    while (at_ < text_.size() &&
           std::isspace(static_cast<unsigned char>(text_[at_]))) {
      ++at_;
    }
  }

  bool take(char c) {
    skip_ws();
    if (at_ < text_.size() && text_[at_] == c) {
      ++at_;
      return true;
    }
    return false;
  }

  void expect(char c) {
    if (!take(c)) {
      throw std::runtime_error("invalid json");
    }
  }

  uint32_t hex4() {
    uint32_t value = 0;
    for (int i = 0; i < 4; ++i) {
      if (at_ >= text_.size()) {
        throw std::runtime_error("short unicode escape");
      }
      const char c = text_[at_++];
      value <<= 4;
      if (c >= '0' && c <= '9') {
        value += static_cast<uint32_t>(c - '0');
      } else if (c >= 'a' && c <= 'f') {
        value += static_cast<uint32_t>(c - 'a' + 10);
      } else if (c >= 'A' && c <= 'F') {
        value += static_cast<uint32_t>(c - 'A' + 10);
      } else {
        throw std::runtime_error("invalid unicode escape");
      }
    }
    return value;
  }

  std::string parse_string() {
    skip_ws();
    if (at_ >= text_.size() || text_[at_++] != '"') {
      throw std::runtime_error("json string expected");
    }
    std::string out;
    while (at_ < text_.size()) {
      const unsigned char c = static_cast<unsigned char>(text_[at_++]);
      if (c == '"') {
        return out;
      }
      if (c != '\\') {
        if (c < 0x20) {
          throw std::runtime_error("control byte in json string");
        }
        out.push_back(static_cast<char>(c));
        continue;
      }
      if (at_ >= text_.size()) {
        throw std::runtime_error("short json escape");
      }
      const char escaped = text_[at_++];
      switch (escaped) {
        case '"':
        case '\\':
        case '/':
          out.push_back(escaped);
          break;
        case 'b':
          out.push_back('\b');
          break;
        case 'f':
          out.push_back('\f');
          break;
        case 'n':
          out.push_back('\n');
          break;
        case 'r':
          out.push_back('\r');
          break;
        case 't':
          out.push_back('\t');
          break;
        case 'u': {
          uint32_t cp = hex4();
          if (cp >= 0xd800 && cp <= 0xdbff) {
            if (at_ + 2 > text_.size() || text_[at_] != '\\' ||
                text_[at_ + 1] != 'u') {
              throw std::runtime_error("missing low surrogate");
            }
            at_ += 2;
            const uint32_t low = hex4();
            if (low < 0xdc00 || low > 0xdfff) {
              throw std::runtime_error("invalid low surrogate");
            }
            cp = 0x10000 + ((cp - 0xd800) << 10) + (low - 0xdc00);
          } else if (cp >= 0xdc00 && cp <= 0xdfff) {
            throw std::runtime_error("unexpected low surrogate");
          }
          append_utf8(&out, cp);
          break;
        }
        default:
          throw std::runtime_error("invalid json escape");
      }
    }
    throw std::runtime_error("unterminated json string");
  }

  std::map<std::string, std::string> parse_string_map() {
    std::map<std::string, std::string> out;
    expect('{');
    skip_ws();
    if (take('}')) {
      return out;
    }
    while (true) {
      const std::string key = parse_string();
      expect(':');
      out[key] = parse_string();
      skip_ws();
      if (take('}')) {
        break;
      }
      expect(',');
    }
    return out;
  }

  void skip_value() {
    skip_ws();
    if (at_ >= text_.size()) {
      throw std::runtime_error("json value expected");
    }
    if (text_[at_] == '"') {
      (void)parse_string();
      return;
    }
    if (take('{')) {
      skip_ws();
      if (take('}')) {
        return;
      }
      while (true) {
        (void)parse_string();
        expect(':');
        skip_value();
        if (take('}')) {
          return;
        }
        expect(',');
      }
    }
    if (take('[')) {
      skip_ws();
      if (take(']')) {
        return;
      }
      while (true) {
        skip_value();
        if (take(']')) {
          return;
        }
        expect(',');
      }
    }
    while (at_ < text_.size() && text_[at_] != ',' && text_[at_] != '}' &&
           text_[at_] != ']' &&
           !std::isspace(static_cast<unsigned char>(text_[at_]))) {
      ++at_;
    }
  }

  const std::string& text_;
  size_t at_ = 0;
};

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
  return Json(blob).parse_item();
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
