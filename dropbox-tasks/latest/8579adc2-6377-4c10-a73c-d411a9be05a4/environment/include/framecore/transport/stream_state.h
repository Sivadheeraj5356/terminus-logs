#pragma once

#include <string>

namespace framecore {

enum class StreamState {
  kIdle,
  kOpen,
  kHalfClosedLocal,
  kHalfClosedRemote,
  kClosed,
};

std::string StreamStateName(StreamState state);
bool CanTransition(StreamState from, StreamState to);

}
