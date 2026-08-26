#pragma once

#include <cstdint>

#include "framecore/byte_reader.h"
#include "framecore/byte_writer.h"
#include "framecore/frame/frame_type.h"
#include "framecore/status.h"

namespace framecore {

struct FrameHeader {
  uint32_t length = 0;
  FrameType type = FrameType::kData;
  uint8_t flags = 0;
  uint32_t stream_id = 0;

  void Serialize(ByteWriter* writer) const;
  static Status Parse(ByteReader* reader, FrameHeader* out);
};

constexpr size_t kFrameHeaderSize = 9;

}
