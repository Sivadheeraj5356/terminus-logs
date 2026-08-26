#include "framecore/logging.h"

#include <cstdio>

namespace framecore {

namespace {

const char* LevelName(LogLevel level) {
  switch (level) {
    case LogLevel::kInfo:
      return "info";
    case LogLevel::kWarn:
      return "warn";
    case LogLevel::kError:
      return "error";
  }
  return "unknown";
}

}

void LogMessage(LogLevel level, const std::string& subsystem, const std::string& message) {
  std::fprintf(stderr, "[%s] %s: %s\n", LevelName(level), subsystem.c_str(), message.c_str());
}

}
