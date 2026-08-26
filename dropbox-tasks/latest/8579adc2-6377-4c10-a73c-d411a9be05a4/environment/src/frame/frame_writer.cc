#include "framecore/frame/frame_writer.h"

#include "framecore/frame/frame_header.h"

namespace framecore {

void FrameWriter::WriteFrame(ByteWriter* writer, FrameType type, uint32_t stream_id, uint8_t flags,
                              const std::vector<uint8_t>& payload) {
  FrameHeader header;
  header.length = static_cast<uint32_t>(payload.size());
  header.type = type;
  header.flags = flags;
  header.stream_id = stream_id;
  header.Serialize(writer);
  writer->WriteBytes(payload);
}

}
