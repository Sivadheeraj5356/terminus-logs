#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "framecore/codec/header_field.h"
#include "framecore/status.h"

namespace framecore {
namespace codec {

std::vector<uint8_t> EncodeHeaderBlock(const std::vector<HeaderField>& headers);
Status DecodeHeaderBlock(const uint8_t* data, size_t len, std::vector<HeaderField>* out);

}
}
