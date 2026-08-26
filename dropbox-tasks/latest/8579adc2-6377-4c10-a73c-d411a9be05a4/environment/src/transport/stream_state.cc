#include "framecore/transport/stream_state.h"

namespace framecore {

std::string StreamStateName(StreamState state) {
  switch (state) {
    case StreamState::kIdle:
      return "idle";
    case StreamState::kOpen:
      return "open";
    case StreamState::kHalfClosedLocal:
      return "half_closed_local";
    case StreamState::kHalfClosedRemote:
      return "half_closed_remote";
    case StreamState::kClosed:
      return "closed";
  }
  return "unknown";
}

bool CanTransition(StreamState from, StreamState to) {
  switch (from) {
    case StreamState::kIdle:
      return to == StreamState::kOpen || to == StreamState::kHalfClosedLocal ||
             to == StreamState::kHalfClosedRemote;
    case StreamState::kOpen:
      return to == StreamState::kHalfClosedLocal || to == StreamState::kHalfClosedRemote ||
             to == StreamState::kClosed;
    case StreamState::kHalfClosedLocal:
      return to == StreamState::kClosed;
    case StreamState::kHalfClosedRemote:
      return to == StreamState::kClosed;
    case StreamState::kClosed:
      return false;
  }
  return false;
}

}
