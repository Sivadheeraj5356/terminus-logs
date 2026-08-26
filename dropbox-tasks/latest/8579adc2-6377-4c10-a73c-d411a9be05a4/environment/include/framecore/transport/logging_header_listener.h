#pragma once

#include <cstdint>
#include <vector>

#include "framecore/codec/header_field.h"
#include "framecore/transport/header_listener.h"
#include "framecore/transport/stream_category.h"

namespace framecore {

class LoggingHeaderListener : public HeaderListener {
 public:
  void OnHeadersComplete(uint32_t stream_id, HeaderCategory category,
                          const std::vector<HeaderField>& headers) override;
};

}
