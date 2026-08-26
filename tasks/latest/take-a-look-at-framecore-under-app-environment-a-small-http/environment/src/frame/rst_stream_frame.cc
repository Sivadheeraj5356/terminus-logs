#include "framecore/frame/rst_stream_frame.h"

#include "framecore/byte_reader.h"
#include "framecore/byte_writer.h"

namespace framecore {

std::vector<uint8_t> RstStreamFrame::EncodePayload() const {
  ByteWriter writer;
  writer.WriteU32BE(error_code);
  return writer.data();
}

Status RstStreamFrame::DecodePayload(const uint8_t* data, size_t len, RstStreamFrame* out) {
  if (len != 4) {
    return Status::InvalidArgument("rst_stream_frame: payload must be 4 bytes");
  }
  ByteReader reader(data, len);
  out->error_code = reader.ReadU32BE();
  return Status::Ok();
}

}
