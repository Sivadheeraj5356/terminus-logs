#include "framecore/transport/connection.h"

#include <utility>

namespace framecore {

Connection::Connection(std::string address, size_t max_session_memory, size_t max_header_count,
                        int64_t initial_window_size)
    : address_(std::move(address)),
      session_(max_session_memory, max_header_count),
      flow_control_(initial_window_size) {}

}
