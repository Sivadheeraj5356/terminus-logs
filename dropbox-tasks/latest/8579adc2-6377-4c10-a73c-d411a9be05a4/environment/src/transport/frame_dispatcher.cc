#include "framecore/transport/frame_dispatcher.h"

#include <string>

#include "framecore/codec/header_block_codec.h"
#include "framecore/frame/frame_type.h"
#include "framecore/frame/goaway_frame.h"
#include "framecore/frame/ping_frame.h"
#include "framecore/frame/rst_stream_frame.h"
#include "framecore/frame/settings_frame.h"
#include "framecore/frame/window_update_frame.h"
#include "framecore/logging.h"
#include "framecore/transport/stream.h"

namespace framecore {

FrameDispatcher::FrameDispatcher(Connection* connection, HeaderListener* listener)
    : connection_(connection), listener_(listener) {}

void FrameDispatcher::DispatchDataFrame(const FrameHeader& header,
                                         const std::vector<uint8_t>& payload) {
  if (!connection_->flow_control().Consume(static_cast<int64_t>(payload.size()))) {
    LogMessage(LogLevel::kWarn, "frame_dispatcher", "data frame exceeded flow control window");
  }
}

void FrameDispatcher::DispatchHeadersFrame(const FrameHeader& header,
                                            const std::vector<uint8_t>& payload) {
  std::vector<HeaderField> fields;
  Status st = codec::DecodeHeaderBlock(payload.data(), payload.size(), &fields);
  if (!st.ok()) {
    LogMessage(LogLevel::kWarn, "frame_dispatcher", "malformed header block");
    return;
  }
  Session& session = connection_->session();
  Stream* stream = session.FindStream(header.stream_id);
  if (stream == nullptr) {
    stream = session.CreateStream(header.stream_id);
  }
  for (const auto& field : fields) {
    stream->AddHeader(field.name, field.value);
  }
  if ((header.flags & kFlagEndHeaders) != 0) {
    std::vector<HeaderField> flushed = stream->FlushHeaders();
    if (listener_ != nullptr) {
      listener_->OnHeadersComplete(header.stream_id, stream->category(), flushed);
    }
  }
}

void FrameDispatcher::DispatchSettingsFrame(const FrameHeader& header,
                                             const std::vector<uint8_t>& payload) {
  SettingsFrame frame;
  if (!SettingsFrame::DecodePayload(payload.data(), payload.size(), &frame).ok()) {
    LogMessage(LogLevel::kWarn, "frame_dispatcher", "malformed settings frame");
    return;
  }
  for (const auto& entry : frame.entries) {
    connection_->settings().Apply(entry.first, entry.second);
  }
}

void FrameDispatcher::DispatchRstStreamFrame(const FrameHeader& header,
                                              const std::vector<uint8_t>& payload) {
  RstStreamFrame frame;
  if (!RstStreamFrame::DecodePayload(payload.data(), payload.size(), &frame).ok()) {
    LogMessage(LogLevel::kWarn, "frame_dispatcher", "malformed rst_stream frame");
    return;
  }
  connection_->session().DestroyStream(header.stream_id);
}

void FrameDispatcher::DispatchGoawayFrame(const FrameHeader& header,
                                           const std::vector<uint8_t>& payload) {
  GoawayFrame frame;
  if (!GoawayFrame::DecodePayload(payload.data(), payload.size(), &frame).ok()) {
    LogMessage(LogLevel::kWarn, "frame_dispatcher", "malformed goaway frame");
    return;
  }
  LogMessage(LogLevel::kInfo, "frame_dispatcher",
             "goaway received, last_stream_id=" + std::to_string(frame.last_stream_id));
}

void FrameDispatcher::DispatchPingFrame(const FrameHeader& header,
                                         const std::vector<uint8_t>& payload) {
  PingFrame frame;
  if (!PingFrame::DecodePayload(payload.data(), payload.size(), &frame).ok()) {
    LogMessage(LogLevel::kWarn, "frame_dispatcher", "malformed ping frame");
  }
}

void FrameDispatcher::DispatchWindowUpdateFrame(const FrameHeader& header,
                                                 const std::vector<uint8_t>& payload) {
  WindowUpdateFrame frame;
  if (!WindowUpdateFrame::DecodePayload(payload.data(), payload.size(), &frame).ok()) {
    LogMessage(LogLevel::kWarn, "frame_dispatcher", "malformed window_update frame");
    return;
  }
  connection_->flow_control().Replenish(static_cast<int64_t>(frame.window_size_increment));
}

}
