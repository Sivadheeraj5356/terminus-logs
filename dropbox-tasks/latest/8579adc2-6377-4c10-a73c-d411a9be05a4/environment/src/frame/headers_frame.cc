#include "framecore/frame/headers_frame.h"

namespace framecore {

std::vector<uint8_t> HeadersFrame::EncodePayload() const { return header_block; }

Status HeadersFrame::DecodePayload(const uint8_t* data, size_t len, HeadersFrame* out) {
  out->header_block.assign(data, data + len);
  return Status::Ok();
}

}
