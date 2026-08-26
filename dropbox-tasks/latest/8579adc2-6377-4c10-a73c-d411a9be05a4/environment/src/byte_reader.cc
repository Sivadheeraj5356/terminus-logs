#include "framecore/byte_reader.h"

namespace framecore {

ByteReader::ByteReader(const uint8_t* data, size_t len) : data_(data), len_(len) {}

bool ByteReader::RequireAvailable(size_t n) {
  if (error_ || pos_ + n > len_) {
    error_ = true;
    return false;
  }
  return true;
}

uint8_t ByteReader::ReadU8() {
  if (!RequireAvailable(1)) return 0;
  uint8_t v = data_[pos_];
  pos_ += 1;
  return v;
}

uint16_t ByteReader::ReadU16BE() {
  if (!RequireAvailable(2)) return 0;
  uint16_t v = (static_cast<uint16_t>(data_[pos_]) << 8) | static_cast<uint16_t>(data_[pos_ + 1]);
  pos_ += 2;
  return v;
}

uint32_t ByteReader::ReadU24BE() {
  if (!RequireAvailable(3)) return 0;
  uint32_t v = (static_cast<uint32_t>(data_[pos_]) << 16) |
               (static_cast<uint32_t>(data_[pos_ + 1]) << 8) |
               static_cast<uint32_t>(data_[pos_ + 2]);
  pos_ += 3;
  return v;
}

uint32_t ByteReader::ReadU32BE() {
  if (!RequireAvailable(4)) return 0;
  uint32_t v = (static_cast<uint32_t>(data_[pos_]) << 24) |
               (static_cast<uint32_t>(data_[pos_ + 1]) << 16) |
               (static_cast<uint32_t>(data_[pos_ + 2]) << 8) |
               static_cast<uint32_t>(data_[pos_ + 3]);
  pos_ += 4;
  return v;
}

uint64_t ByteReader::ReadU64BE() {
  if (!RequireAvailable(8)) return 0;
  uint64_t v = 0;
  for (size_t i = 0; i < 8; ++i) {
    v = (v << 8) | static_cast<uint64_t>(data_[pos_ + i]);
  }
  pos_ += 8;
  return v;
}

std::vector<uint8_t> ByteReader::ReadBytes(size_t n) {
  if (!RequireAvailable(n)) return {};
  std::vector<uint8_t> out(data_ + pos_, data_ + pos_ + n);
  pos_ += n;
  return out;
}

size_t ByteReader::Remaining() const { return pos_ > len_ ? 0 : len_ - pos_; }

}
