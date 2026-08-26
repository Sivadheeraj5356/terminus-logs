#include "framecore/transport/flow_control.h"

namespace framecore {

FlowControlWindow::FlowControlWindow(int64_t initial_size) : available_(initial_size) {}

bool FlowControlWindow::Consume(int64_t bytes) {
  if (bytes < 0 || bytes > available_) {
    return false;
  }
  available_ -= bytes;
  return true;
}

void FlowControlWindow::Replenish(int64_t bytes) { available_ += bytes; }

}
