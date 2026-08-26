#pragma once

#include <string>

namespace framecore {

enum class StatusCode {
  kOk = 0,
  kIgnored = 1,
  kResourceExhausted = 2,
  kInvalidArgument = 3,
};

class Status {
 public:
  static Status Ok();
  static Status Ignored(std::string message);
  static Status ResourceExhausted(std::string message);
  static Status InvalidArgument(std::string message);

  bool ok() const { return code_ == StatusCode::kOk; }
  bool ignored() const { return code_ == StatusCode::kIgnored; }
  StatusCode code() const { return code_; }
  const std::string& message() const { return message_; }

 private:
  Status(StatusCode code, std::string message);

  StatusCode code_;
  std::string message_;
};

}
