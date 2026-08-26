#include "framecore/transport/session_manager.h"

#include <utility>

namespace framecore {

Connection* SessionManager::OpenConnection(const std::string& address, size_t max_session_memory,
                                            size_t max_header_count, int64_t initial_window_size) {
  auto connection = std::make_unique<Connection>(address, max_session_memory, max_header_count,
                                                  initial_window_size);
  Connection* raw = connection.get();
  connections_.push_back(std::move(connection));
  return raw;
}

}
