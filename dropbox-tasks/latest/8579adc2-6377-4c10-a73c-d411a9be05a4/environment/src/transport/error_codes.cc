#include "framecore/transport/error_codes.h"

namespace framecore {

std::string ErrorCodeName(ErrorCode code) {
  switch (code) {
    case ErrorCode::kNoError:
      return "no_error";
    case ErrorCode::kProtocolError:
      return "protocol_error";
    case ErrorCode::kInternalError:
      return "internal_error";
    case ErrorCode::kFlowControlError:
      return "flow_control_error";
    case ErrorCode::kSettingsTimeout:
      return "settings_timeout";
    case ErrorCode::kStreamClosed:
      return "stream_closed";
    case ErrorCode::kFrameSizeError:
      return "frame_size_error";
    case ErrorCode::kRefusedStream:
      return "refused_stream";
    case ErrorCode::kCancel:
      return "cancel";
    case ErrorCode::kCompressionError:
      return "compression_error";
    case ErrorCode::kConnectError:
      return "connect_error";
    case ErrorCode::kEnhanceYourCalm:
      return "enhance_your_calm";
    case ErrorCode::kInadequateSecurity:
      return "inadequate_security";
  }
  return "unknown_error";
}

}
