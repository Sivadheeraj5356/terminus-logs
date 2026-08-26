#include "framecore/varint.h"

namespace framecore {

void EncodeVarint(uint64_t value, std::vector<uint8_t>* out) {
  while (value >= 0x80) {
    out->push_back(static_cast<uint8_t>(value & 0x7f) | 0x80);
    value >>= 7;
  }
  out->push_back(static_cast<uint8_t>(value & 0x7f));
}

bool DecodeVarint(const uint8_t* data, size_t len, uint64_t* value, size_t* consumed) {
  uint64_t result = 0;
  size_t shift = 0;
  size_t i = 0;
  while (true) {
    if (i >= len || i >= 10) return false;
    uint8_t byte = data[i];
    result |= static_cast<uint64_t>(byte & 0x7f) << shift;
    ++i;
    if ((byte & 0x80) == 0) break;
    shift += 7;
  }
  *value = result;
  *consumed = i;
  return true;
}

}
