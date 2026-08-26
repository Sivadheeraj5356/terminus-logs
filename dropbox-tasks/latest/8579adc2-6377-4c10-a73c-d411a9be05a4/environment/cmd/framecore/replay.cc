#include "replay.h"

#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include "framecore/byte_reader.h"
#include "framecore/status.h"
#include "framecore/frame/frame_reader.h"
#include "framecore/frame/frame_type.h"

namespace framecore {
namespace cli {

namespace {

std::string FrameTypeName(FrameType type) {
  switch (type) {
    case FrameType::kData:
      return "data";
    case FrameType::kHeaders:
      return "headers";
    case FrameType::kSettings:
      return "settings";
    case FrameType::kRstStream:
      return "rst_stream";
    case FrameType::kGoaway:
      return "goaway";
    case FrameType::kPing:
      return "ping";
    case FrameType::kWindowUpdate:
      return "window_update";
  }
  return "unknown";
}

}

int RunReplay(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    std::fprintf(stderr, "replay: cannot open capture %s\n", path.c_str());
    return 2;
  }
  std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(in)),
                              std::istreambuf_iterator<char>());

  ByteReader reader(bytes.data(), bytes.size());
  int frame_count = 0;
  while (reader.Remaining() > 0) {
    ParsedFrame frame;
    Status st = FrameReader::ReadFrame(&reader, &frame);
    if (!st.ok()) {
      std::fprintf(stderr, "replay: %s\n", st.message().c_str());
      return 1;
    }
    std::printf("FRAME type=%s stream_id=%u length=%u flags=%u\n",
                FrameTypeName(frame.header.type).c_str(), frame.header.stream_id,
                frame.header.length, frame.header.flags);
    ++frame_count;
  }
  std::printf("REPLAY frames=%d\n", frame_count);
  return 0;
}

}
}
