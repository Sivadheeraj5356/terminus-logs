#include "framecore/frame/goaway_frame.h"

#include "framecore/byte_reader.h"
#include "framecore/byte_writer.h"

namespace framecore {

std::vector<uint8_t> GoawayFrame::EncodePayload() const {
  ByteWriter writer;
  writer.WriteU32BE(last_stream_id);
  writer.WriteU32BE(error_code);
  writer.WriteBytes(debug_data);
  return writer.data();
}

Status GoawayFrame::DecodePayload(const uint8_t* data, size_t len, GoawayFrame* out) {
  if (len < 8) {
    return Status::InvalidArgument("goaway_frame: payload shorter than 8 bytes");
  }
  ByteReader reader(data, len);
  out->last_stream_id = reader.ReadU32BE();
  out->error_code = reader.ReadU32BE();
  out->debug_data = reader.ReadBytes(reader.Remaining());
  return Status::Ok();
}

}
