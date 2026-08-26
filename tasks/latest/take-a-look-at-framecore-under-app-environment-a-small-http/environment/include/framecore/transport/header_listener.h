#pragma once

#include <cstdint>
#include <vector>

#include "framecore/codec/header_field.h"
#include "framecore/transport/stream_category.h"

namespace framecore {

class HeaderListener {
 public:
  virtual ~HeaderListener() = default;
  virtual void OnHeadersComplete(uint32_t stream_id, HeaderCategory category,
                                  const std::vector<HeaderField>& headers) = 0;
};

}
