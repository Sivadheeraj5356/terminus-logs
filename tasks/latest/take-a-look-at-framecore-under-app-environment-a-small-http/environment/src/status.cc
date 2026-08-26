#include "framecore/status.h"

#include <utility>

namespace framecore {

Status::Status(StatusCode code, std::string message)
    : code_(code), message_(std::move(message)) {}

Status Status::Ok() { return Status(StatusCode::kOk, ""); }

Status Status::Ignored(std::string message) {
  return Status(StatusCode::kIgnored, std::move(message));
}

Status Status::ResourceExhausted(std::string message) {
  return Status(StatusCode::kResourceExhausted, std::move(message));
}

Status Status::InvalidArgument(std::string message) {
  return Status(StatusCode::kInvalidArgument, std::move(message));
}

}
