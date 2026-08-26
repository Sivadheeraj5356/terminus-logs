#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace framecore {

class ByteReader {
 public:
  ByteReader(const uint8_t* data, size_t len);

  uint8_t ReadU8();
  uint16_t ReadU16BE();
  uint32_t ReadU24BE();
  uint32_t ReadU32BE();
  uint64_t ReadU64BE();
  std::vector<uint8_t> ReadBytes(size_t n);

  size_t Remaining() const;
  bool ok() const { return !error_; }

 private:
  bool RequireAvailable(size_t n);

  const uint8_t* data_;
  size_t len_;
  size_t pos_ = 0;
  bool error_ = false;
};

}
