#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include "framecore/byte_reader.h"
#include "framecore/codec/header_block_codec.h"
#include "framecore/codec/header_field.h"
#include "framecore/frame/frame_reader.h"
#include "framecore/frame/frame_type.h"
#include "framecore/status.h"

int main(int argc, char** argv) {
  if (argc != 2) {
    std::fprintf(stderr, "usage: decode_wire_capture <path>\n");
    return 2;
  }
  std::ifstream in(argv[1], std::ios::binary);
  if (!in) {
    std::fprintf(stderr, "decode_wire_capture: cannot open %s\n", argv[1]);
    return 2;
  }
  std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(in)),
                              std::istreambuf_iterator<char>());

  framecore::ByteReader reader(bytes.data(), bytes.size());
  framecore::ParsedFrame frame;
  framecore::Status st = framecore::FrameReader::ReadFrame(&reader, &frame);
  if (!st.ok()) {
    std::fprintf(stderr, "decode_wire_capture: %s\n", st.message().c_str());
    return 1;
  }
  if (frame.header.type == framecore::FrameType::kHeaders) {
    std::vector<framecore::HeaderField> fields;
    if (framecore::codec::DecodeHeaderBlock(frame.raw_payload.data(), frame.raw_payload.size(),
                                             &fields)
            .ok()) {
      for (const auto& field : fields) {
        std::printf("%s: %s\n", field.name.c_str(), field.value.c_str());
      }
    }
  } else {
    std::printf("non-headers frame, %zu payload bytes\n", frame.raw_payload.size());
  }
  return 0;
}
