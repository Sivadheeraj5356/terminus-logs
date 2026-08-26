#pragma once

#include <cstdint>
#include <vector>

#include "framecore/byte_writer.h"
#include "framecore/frame/frame_type.h"

namespace framecore {

class FrameWriter {
 public:
  static void WriteFrame(ByteWriter* writer, FrameType type, uint32_t stream_id, uint8_t flags,
                          const std::vector<uint8_t>& payload);
};

}
