#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace framecore {

class ByteWriter {
 public:
  ByteWriter() = default;

  void WriteU8(uint8_t v);
  void WriteU16BE(uint16_t v);
  void WriteU24BE(uint32_t v);
  void WriteU32BE(uint32_t v);
  void WriteU64BE(uint64_t v);
  void WriteBytes(const uint8_t* data, size_t n);
  void WriteBytes(const std::vector<uint8_t>& data);

  const std::vector<uint8_t>& data() const { return buf_; }
  size_t size() const { return buf_.size(); }

 private:
  std::vector<uint8_t> buf_;
};

}
