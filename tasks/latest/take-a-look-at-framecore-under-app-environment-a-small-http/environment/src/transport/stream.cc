#include "framecore/transport/stream.h"

#include <utility>

#include "framecore/transport/session.h"

namespace framecore {

Stream::Stream(uint32_t stream_id, Session* session)
    : stream_id_(stream_id), session_(session) {}

Stream::~Stream() {}

Status Stream::StartHeaders(HeaderCategory category) {
  phase_started_ = true;
  current_headers_length_ = 0;
  current_headers_.clear();
  category_ = category;
  return Status::Ok();
}

Status Stream::AddHeader(const std::string& name, const std::string& value) {
  size_t charge = name.size() + value.size() + kHeaderOverheadBytes;
  if (!session_->IsAvailableSessionMemory(charge) || !session_->IsAvailableHeaderCount(1)) {
    return Status::ResourceExhausted(
        "stream: header budget exceeded for stream " + std::to_string(stream_id_));
  }
  session_->IncrementCurrentSessionMemory(charge);
  session_->IncrementHeaderCount(1);
  current_headers_length_ += charge;
  current_headers_.push_back(HeaderField{name, value});
  return Status::Ok();
}

std::vector<HeaderField> Stream::FlushHeaders() {
  std::vector<HeaderField> flushed = std::move(current_headers_);
  return flushed;
}

}
