#include "framecore/byte_writer.h"

namespace framecore {

void ByteWriter::WriteU8(uint8_t v) { buf_.push_back(v); }

void ByteWriter::WriteU16BE(uint16_t v) {
  buf_.push_back(static_cast<uint8_t>((v >> 8) & 0xff));
  buf_.push_back(static_cast<uint8_t>(v & 0xff));
}

void ByteWriter::WriteU24BE(uint32_t v) {
  buf_.push_back(static_cast<uint8_t>((v >> 16) & 0xff));
  buf_.push_back(static_cast<uint8_t>((v >> 8) & 0xff));
  buf_.push_back(static_cast<uint8_t>(v & 0xff));
}

void ByteWriter::WriteU32BE(uint32_t v) {
  buf_.push_back(static_cast<uint8_t>((v >> 24) & 0xff));
  buf_.push_back(static_cast<uint8_t>((v >> 16) & 0xff));
  buf_.push_back(static_cast<uint8_t>((v >> 8) & 0xff));
  buf_.push_back(static_cast<uint8_t>(v & 0xff));
}

void ByteWriter::WriteU64BE(uint64_t v) {
  for (int shift = 56; shift >= 0; shift -= 8) {
    buf_.push_back(static_cast<uint8_t>((v >> shift) & 0xff));
  }
}

void ByteWriter::WriteBytes(const uint8_t* data, size_t n) {
  buf_.insert(buf_.end(), data, data + n);
}

void ByteWriter::WriteBytes(const std::vector<uint8_t>& data) {
  buf_.insert(buf_.end(), data.begin(), data.end());
}

}
