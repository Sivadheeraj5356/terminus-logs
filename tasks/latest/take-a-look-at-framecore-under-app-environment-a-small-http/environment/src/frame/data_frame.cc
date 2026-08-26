#include "framecore/frame/data_frame.h"

namespace framecore {

std::vector<uint8_t> DataFrame::EncodePayload() const { return payload; }

Status DataFrame::DecodePayload(const uint8_t* data, size_t len, DataFrame* out) {
  out->payload.assign(data, data + len);
  return Status::Ok();
}

}
