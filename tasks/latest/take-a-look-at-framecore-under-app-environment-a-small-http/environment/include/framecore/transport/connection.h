#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

#include "framecore/transport/flow_control.h"
#include "framecore/transport/session.h"
#include "framecore/transport/settings_registry.h"

namespace framecore {

class Connection {
 public:
  Connection(std::string address, size_t max_session_memory, size_t max_header_count,
             int64_t initial_window_size);

  const std::string& address() const { return address_; }
  Session& session() { return session_; }
  FlowControlWindow& flow_control() { return flow_control_; }
  SettingsRegistry& settings() { return settings_; }

 private:
  std::string address_;
  Session session_;
  FlowControlWindow flow_control_;
  SettingsRegistry settings_;
};

}
