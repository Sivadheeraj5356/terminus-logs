#include <cstdint>
#include <cstdio>
#include <vector>

#include "framecore/byte_writer.h"
#include "framecore/codec/header_block_codec.h"
#include "framecore/codec/header_field.h"
#include "framecore/frame/frame_type.h"
#include "framecore/frame/frame_writer.h"

int main() {
  std::vector<framecore::HeaderField> fields = {
      {":method", "GET"},
      {":path", "/"},
      {"host", "example.test"},
  };
  std::vector<uint8_t> header_block = framecore::codec::EncodeHeaderBlock(fields);

  framecore::ByteWriter writer;
  framecore::FrameWriter::WriteFrame(&writer, framecore::FrameType::kHeaders,
                                      /*stream_id=*/1, framecore::kFlagEndHeaders, header_block);

  std::printf("encoded %zu bytes for a single HEADERS frame\n", writer.size());
  return 0;
}
