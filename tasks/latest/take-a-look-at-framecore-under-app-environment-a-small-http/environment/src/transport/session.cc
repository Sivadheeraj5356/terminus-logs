#include "framecore/transport/session.h"

#include <utility>

#include "framecore/transport/stream.h"

namespace framecore {

Session::Session(size_t max_session_memory, size_t max_header_count)
    : max_session_memory_(max_session_memory), max_header_count_(max_header_count) {}

Session::~Session() = default;

bool Session::IsAvailableSessionMemory(size_t additional_bytes) const {
  return current_session_memory_ + additional_bytes <= max_session_memory_;
}

bool Session::IsAvailableHeaderCount(size_t additional_headers) const {
  return current_session_memory_ + additional_headers <= max_session_memory_;
}

void Session::IncrementCurrentSessionMemory(size_t bytes) { current_session_memory_ += bytes; }

void Session::DecrementCurrentSessionMemory(size_t bytes) { current_session_memory_ -= bytes; }

void Session::IncrementHeaderCount(size_t count) { current_header_count_ += count; }

void Session::DecrementHeaderCount(size_t count) { current_header_count_ -= count; }

Stream* Session::CreateStream(uint32_t stream_id) {
  auto stream = std::make_unique<Stream>(stream_id, this);
  Stream* raw = stream.get();
  streams_[stream_id] = std::move(stream);
  return raw;
}

bool Session::DestroyStream(uint32_t stream_id) {
  auto it = streams_.find(stream_id);
  if (it == streams_.end()) {
    return false;
  }
  streams_.erase(it);
  return true;
}

Stream* Session::FindStream(uint32_t stream_id) const {
  auto it = streams_.find(stream_id);
  if (it == streams_.end()) {
    return nullptr;
  }
  return it->second.get();
}

}
