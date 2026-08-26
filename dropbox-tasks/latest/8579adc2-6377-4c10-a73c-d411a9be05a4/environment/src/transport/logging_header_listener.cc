#include "framecore/transport/logging_header_listener.h"

#include <string>

#include "framecore/logging.h"

namespace framecore {

namespace {

std::string CategoryName(HeaderCategory category) {
  switch (category) {
    case HeaderCategory::kHeaders:
      return "headers";
    case HeaderCategory::kInformational:
      return "informational";
    case HeaderCategory::kTrailers:
      return "trailers";
  }
  return "unknown";
}

}

void LoggingHeaderListener::OnHeadersComplete(uint32_t stream_id, HeaderCategory category,
                                               const std::vector<HeaderField>& headers) {
  LogMessage(LogLevel::kInfo, "logging_header_listener",
             "stream " + std::to_string(stream_id) + " delivered " +
                 std::to_string(headers.size()) + " " + CategoryName(category) + " headers");
}

}
