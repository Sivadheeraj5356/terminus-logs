#include "framecore/frame/frame_reader.h"

#include <utility>

namespace framecore {

Status FrameReader::ReadFrame(ByteReader* reader, ParsedFrame* out) {
  FrameHeader header;
  Status st = FrameHeader::Parse(reader, &header);
  if (!st.ok()) {
    return st;
  }
  std::vector<uint8_t> payload = reader->ReadBytes(header.length);
  if (!reader->ok()) {
    return Status::InvalidArgument("frame_reader: truncated frame payload");
  }
  out->header = header;
  out->raw_payload = std::move(payload);
  return Status::Ok();
}

}
