#pragma once

#include "pam_lab/types.hpp"

#include <cstdint>
#include <string>
#include <string_view>
#include <utility>

namespace pam_lab {

enum class EventKind {
    FailIncrement,
    FailReset,
    TokenConsume,
    SessionOpen,
    SessionClose,
    AuthDenied,
};

struct Event {
    EventKind kind{EventKind::AuthDenied};
    std::string first;
    std::string second;
    std::string third;

    [[nodiscard]] bool durable() const;
};

std::string encode_event(std::uint64_t sequence, const Event& event);
std::pair<std::uint64_t, Event> decode_event(std::string_view line);

}  // namespace pam_lab
