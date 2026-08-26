#include "framecore/frame/ping_frame.h"

#include "framecore/byte_reader.h"
#include "framecore/byte_writer.h"

namespace framecore {

std::vector<uint8_t> PingFrame::EncodePayload() const {
  ByteWriter writer;
  writer.WriteU64BE(opaque_data);
  return writer.data();
}

Status PingFrame::DecodePayload(const uint8_t* data, size_t len, PingFrame* out) {
  if (len != 8) {
    return Status::InvalidArgument("ping_frame: payload must be 8 bytes");
  }
  ByteReader reader(data, len);
  out->opaque_data = reader.ReadU64BE();
  return Status::Ok();
}

}
