#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace framecore {

class RingBuffer {
 public:
  explicit RingBuffer(size_t capacity);

  size_t Write(const uint8_t* data, size_t n);
  size_t Read(uint8_t* out, size_t n);

  size_t size() const { return size_; }
  size_t capacity() const { return buf_.size(); }
  bool empty() const { return size_ == 0; }
  bool full() const { return size_ == buf_.size(); }

 private:
  std::vector<uint8_t> buf_;
  size_t head_ = 0;
  size_t size_ = 0;
};

}
