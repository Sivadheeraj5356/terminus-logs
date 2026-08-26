#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "framecore/codec/header_field.h"
#include "framecore/status.h"
#include "framecore/transport/stream_category.h"

namespace framecore {

class Session;

inline constexpr size_t kHeaderOverheadBytes = 32;

class Stream {
 public:
  Stream(uint32_t stream_id, Session* session);
  ~Stream();

  Stream(const Stream&) = delete;
  Stream& operator=(const Stream&) = delete;

  Status StartHeaders(HeaderCategory category);
  Status AddHeader(const std::string& name, const std::string& value);
  std::vector<HeaderField> FlushHeaders();

  uint32_t stream_id() const { return stream_id_; }
  HeaderCategory category() const { return category_; }
  size_t current_headers_length() const { return current_headers_length_; }
  size_t header_count() const { return current_headers_.size(); }

 private:
  uint32_t stream_id_;
  Session* session_;
  HeaderCategory category_ = HeaderCategory::kHeaders;
  bool phase_started_ = false;
  size_t current_headers_length_ = 0;
  std::vector<HeaderField> current_headers_;
};

}
