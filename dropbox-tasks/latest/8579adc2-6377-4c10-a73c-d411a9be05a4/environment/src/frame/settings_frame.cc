#include "framecore/frame/settings_frame.h"

#include "framecore/byte_reader.h"
#include "framecore/byte_writer.h"

namespace framecore {

std::vector<uint8_t> SettingsFrame::EncodePayload() const {
  ByteWriter writer;
  for (const auto& entry : entries) {
    writer.WriteU16BE(entry.first);
    writer.WriteU32BE(entry.second);
  }
  return writer.data();
}

Status SettingsFrame::DecodePayload(const uint8_t* data, size_t len, SettingsFrame* out) {
  if (len % 6 != 0) {
    return Status::InvalidArgument("settings_frame: payload length not a multiple of 6");
  }
  ByteReader reader(data, len);
  out->entries.clear();
  while (reader.Remaining() > 0) {
    uint16_t id = reader.ReadU16BE();
    uint32_t value = reader.ReadU32BE();
    if (!reader.ok()) {
      return Status::InvalidArgument("settings_frame: truncated entry");
    }
    out->entries.emplace_back(id, value);
  }
  return Status::Ok();
}

}
