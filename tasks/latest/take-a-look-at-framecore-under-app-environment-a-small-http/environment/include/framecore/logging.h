#pragma once

#include <string>

namespace framecore {

enum class LogLevel {
  kInfo = 0,
  kWarn = 1,
  kError = 2,
};

void LogMessage(LogLevel level, const std::string& subsystem, const std::string& message);

}
