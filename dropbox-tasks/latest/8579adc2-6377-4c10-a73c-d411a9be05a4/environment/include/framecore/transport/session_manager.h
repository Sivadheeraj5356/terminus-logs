#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "framecore/transport/connection.h"

namespace framecore {

class SessionManager {
 public:
  Connection* OpenConnection(const std::string& address, size_t max_session_memory,
                              size_t max_header_count, int64_t initial_window_size);
  size_t connection_count() const { return connections_.size(); }

 private:
  std::vector<std::unique_ptr<Connection>> connections_;
};

}
