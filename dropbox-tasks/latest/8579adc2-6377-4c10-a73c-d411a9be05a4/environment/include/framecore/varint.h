#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace framecore {

void EncodeVarint(uint64_t value, std::vector<uint8_t>* out);
bool DecodeVarint(const uint8_t* data, size_t len, uint64_t* value, size_t* consumed);

}
