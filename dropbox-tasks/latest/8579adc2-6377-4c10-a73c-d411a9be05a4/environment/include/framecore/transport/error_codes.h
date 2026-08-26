#pragma once

#include <cstdint>
#include <string>

namespace framecore {

enum class ErrorCode : uint32_t {
  kNoError = 0,
  kProtocolError = 1,
  kInternalError = 2,
  kFlowControlError = 3,
  kSettingsTimeout = 4,
  kStreamClosed = 5,
  kFrameSizeError = 6,
  kRefusedStream = 7,
  kCancel = 8,
  kCompressionError = 9,
  kConnectError = 10,
  kEnhanceYourCalm = 11,
  kInadequateSecurity = 12,
};

std::string ErrorCodeName(ErrorCode code);

}
