#include "framecore/frame/window_update_frame.h"

#include "framecore/byte_reader.h"
#include "framecore/byte_writer.h"

namespace framecore {

std::vector<uint8_t> WindowUpdateFrame::EncodePayload() const {
  ByteWriter writer;
  writer.WriteU32BE(window_size_increment);
  return writer.data();
}

Status WindowUpdateFrame::DecodePayload(const uint8_t* data, size_t len, WindowUpdateFrame* out) {
  if (len != 4) {
    return Status::InvalidArgument("window_update_frame: payload must be 4 bytes");
  }
  ByteReader reader(data, len);
  out->window_size_increment = reader.ReadU32BE();
  return Status::Ok();
}

}
