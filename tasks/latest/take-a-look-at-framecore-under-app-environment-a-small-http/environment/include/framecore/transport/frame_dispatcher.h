#pragma once

#include <cstdint>
#include <vector>

#include "framecore/frame/frame_header.h"
#include "framecore/transport/connection.h"
#include "framecore/transport/header_listener.h"

namespace framecore {

class FrameDispatcher {
 public:
  FrameDispatcher(Connection* connection, HeaderListener* listener);

  void DispatchDataFrame(const FrameHeader& header, const std::vector<uint8_t>& payload);
  void DispatchHeadersFrame(const FrameHeader& header, const std::vector<uint8_t>& payload);
  void DispatchSettingsFrame(const FrameHeader& header, const std::vector<uint8_t>& payload);
  void DispatchRstStreamFrame(const FrameHeader& header, const std::vector<uint8_t>& payload);
  void DispatchGoawayFrame(const FrameHeader& header, const std::vector<uint8_t>& payload);
  void DispatchPingFrame(const FrameHeader& header, const std::vector<uint8_t>& payload);
  void DispatchWindowUpdateFrame(const FrameHeader& header, const std::vector<uint8_t>& payload);

 private:
  Connection* connection_;
  HeaderListener* listener_;
};

}
