#include "framecore/config/config_loader.h"

#include <fstream>
#include <sstream>
#include <string>

namespace framecore {

namespace {

bool ParseSizeField(const std::string& key, const std::string& value, const std::string& field,
                     size_t* out) {
  if (key != field) {
    return false;
  }
  try {
    *out = static_cast<size_t>(std::stoull(value));
  } catch (const std::exception&) {
    return false;
  }
  return true;
}

}

Config LoadConfig(const std::string& path) {
  Config config;
  if (path.empty()) {
    return config;
  }
  std::ifstream in(path);
  if (!in) {
    return config;
  }
  std::string line;
  while (std::getline(in, line)) {
    size_t eq = line.find('=');
    if (eq == std::string::npos) {
      continue;
    }
    std::string key = line.substr(0, eq);
    std::string value = line.substr(eq + 1);
    if (ParseSizeField(key, value, "max_session_memory", &config.max_session_memory)) continue;
    if (ParseSizeField(key, value, "max_header_count", &config.max_header_count)) continue;
    if (ParseSizeField(key, value, "max_concurrent_streams", &config.max_concurrent_streams)) {
      continue;
    }
    if (ParseSizeField(key, value, "initial_window_size", &config.initial_window_size)) continue;
    if (ParseSizeField(key, value, "max_frame_size", &config.max_frame_size)) continue;
  }
  return config;
}

}
