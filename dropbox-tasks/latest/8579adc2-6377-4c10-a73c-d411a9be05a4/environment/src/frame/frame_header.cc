#include "framecore/frame/frame_header.h"

namespace framecore {

void FrameHeader::Serialize(ByteWriter* writer) const {
  writer->WriteU24BE(length);
  writer->WriteU8(static_cast<uint8_t>(type));
  writer->WriteU8(flags);
  writer->WriteU32BE(stream_id);
}

Status FrameHeader::Parse(ByteReader* reader, FrameHeader* out) {
  uint32_t length = reader->ReadU24BE();
  uint8_t raw_type = reader->ReadU8();
  uint8_t flags = reader->ReadU8();
  uint32_t stream_id = reader->ReadU32BE();
  if (!reader->ok()) {
    return Status::InvalidArgument("frame_header: truncated frame header");
  }
  if (raw_type > static_cast<uint8_t>(FrameType::kWindowUpdate)) {
    return Status::InvalidArgument("frame_header: unknown frame type");
  }
  out->length = length;
  out->type = static_cast<FrameType>(raw_type);
  out->flags = flags;
  out->stream_id = stream_id;
  return Status::Ok();
}

}
