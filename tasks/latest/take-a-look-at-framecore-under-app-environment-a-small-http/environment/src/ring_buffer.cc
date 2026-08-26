#include "framecore/ring_buffer.h"

#include <algorithm>

namespace framecore {

RingBuffer::RingBuffer(size_t capacity) : buf_(capacity) {}

size_t RingBuffer::Write(const uint8_t* data, size_t n) {
  size_t cap = buf_.size();
  if (cap == 0) return 0;
  size_t free_space = cap - size_;
  size_t to_write = std::min(n, free_space);
  size_t tail = (head_ + size_) % cap;
  for (size_t i = 0; i < to_write; ++i) {
    buf_[(tail + i) % cap] = data[i];
  }
  size_ += to_write;
  return to_write;
}

size_t RingBuffer::Read(uint8_t* out, size_t n) {
  size_t to_read = std::min(n, size_);
  for (size_t i = 0; i < to_read; ++i) {
    out[i] = buf_[(head_ + i) % buf_.size()];
  }
  head_ = (head_ + to_read) % buf_.size();
  size_ -= to_read;
  return to_read;
}

}
