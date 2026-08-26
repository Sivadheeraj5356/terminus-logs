#pragma once

#include <cstdint>

namespace framecore {

class FlowControlWindow {
 public:
  explicit FlowControlWindow(int64_t initial_size);

  bool Consume(int64_t bytes);
  void Replenish(int64_t bytes);

  int64_t available() const { return available_; }

 private:
  int64_t available_;
};

}
