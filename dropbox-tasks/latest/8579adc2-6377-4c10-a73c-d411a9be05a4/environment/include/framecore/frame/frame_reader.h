#pragma once

#include <cstdint>
#include <vector>

#include "framecore/byte_reader.h"
#include "framecore/frame/frame_header.h"
#include "framecore/status.h"

namespace framecore {

struct ParsedFrame {
  FrameHeader header;
  std::vector<uint8_t> raw_payload;
};

class FrameReader {
 public:
  static Status ReadFrame(ByteReader* reader, ParsedFrame* out);
};

}
