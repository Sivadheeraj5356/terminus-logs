#include "framecore/codec/header_block_codec.h"

#include <string>
#include <utility>

#include "framecore/varint.h"

namespace framecore {
namespace codec {

std::vector<uint8_t> EncodeHeaderBlock(const std::vector<HeaderField>& headers) {
  std::vector<uint8_t> out;
  for (const auto& field : headers) {
    EncodeVarint(field.name.size(), &out);
    out.insert(out.end(), field.name.begin(), field.name.end());
    EncodeVarint(field.value.size(), &out);
    out.insert(out.end(), field.value.begin(), field.value.end());
  }
  return out;
}

Status DecodeHeaderBlock(const uint8_t* data, size_t len, std::vector<HeaderField>* out) {
  out->clear();
  size_t pos = 0;
  while (pos < len) {
    uint64_t name_len = 0;
    size_t consumed = 0;
    if (!DecodeVarint(data + pos, len - pos, &name_len, &consumed)) {
      return Status::InvalidArgument("header_block_codec: truncated name length");
    }
    pos += consumed;
    if (pos + name_len > len) {
      return Status::InvalidArgument("header_block_codec: truncated name bytes");
    }
    std::string name(reinterpret_cast<const char*>(data + pos), name_len);
    pos += name_len;

    uint64_t value_len = 0;
    if (!DecodeVarint(data + pos, len - pos, &value_len, &consumed)) {
      return Status::InvalidArgument("header_block_codec: truncated value length");
    }
    pos += consumed;
    if (pos + value_len > len) {
      return Status::InvalidArgument("header_block_codec: truncated value bytes");
    }
    std::string value(reinterpret_cast<const char*>(data + pos), value_len);
    pos += value_len;

    out->push_back(HeaderField{std::move(name), std::move(value)});
  }
  return Status::Ok();
}

}
}
