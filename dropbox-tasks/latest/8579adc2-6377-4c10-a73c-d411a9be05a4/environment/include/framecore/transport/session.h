#pragma once

#include <cstddef>
#include <cstdint>
#include <map>
#include <memory>

namespace framecore {

class Stream;

class Session {
 public:
  Session(size_t max_session_memory, size_t max_header_count);
  ~Session();

  Session(const Session&) = delete;
  Session& operator=(const Session&) = delete;

  bool IsAvailableSessionMemory(size_t additional_bytes) const;
  bool IsAvailableHeaderCount(size_t additional_headers) const;

  void IncrementCurrentSessionMemory(size_t bytes);
  void DecrementCurrentSessionMemory(size_t bytes);
  void IncrementHeaderCount(size_t count);
  void DecrementHeaderCount(size_t count);

  size_t current_session_memory() const { return current_session_memory_; }
  size_t current_header_count() const { return current_header_count_; }
  size_t max_session_memory() const { return max_session_memory_; }
  size_t max_header_count() const { return max_header_count_; }

  Stream* CreateStream(uint32_t stream_id);
  bool DestroyStream(uint32_t stream_id);
  Stream* FindStream(uint32_t stream_id) const;
  size_t stream_count() const { return streams_.size(); }

 private:
  size_t max_session_memory_;
  size_t max_header_count_;
  size_t current_session_memory_ = 0;
  size_t current_header_count_ = 0;
  std::map<uint32_t, std::unique_ptr<Stream>> streams_;
};

}
