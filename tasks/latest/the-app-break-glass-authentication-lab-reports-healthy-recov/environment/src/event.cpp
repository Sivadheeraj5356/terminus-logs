#include "pam_lab/event.hpp"

#include "pam_lab/io.hpp"

#include <charconv>
#include <stdexcept>

namespace pam_lab {
namespace {

std::uint64_t parse_sequence(std::string_view value) {
    std::uint64_t sequence = 0;
    const auto result = std::from_chars(value.data(), value.data() + value.size(), sequence);
    if (result.ec != std::errc{} || result.ptr != value.data() + value.size()) {
        throw std::runtime_error("invalid event sequence");
    }
    return sequence;
}

std::string event_name(EventKind kind) {
    switch (kind) {
        case EventKind::FailIncrement:
            return "fail_increment";
        case EventKind::FailReset:
            return "fail_reset";
        case EventKind::TokenConsume:
            return "token_consume";
        case EventKind::SessionOpen:
            return "session_open";
        case EventKind::SessionClose:
            return "session_close";
        case EventKind::AuthDenied:
            return "auth_denied";
    }
    throw std::runtime_error("unknown event kind");
}

}  // namespace

bool Event::durable() const {
    switch (kind) {
        case EventKind::FailReset:
            return false;
        case EventKind::SessionClose:
            return false;
        case EventKind::FailIncrement:
        case EventKind::TokenConsume:
        case EventKind::SessionOpen:
        case EventKind::AuthDenied:
            return true;
    }
    throw std::runtime_error("unknown event kind");
}

std::string encode_event(std::uint64_t sequence, const Event& event) {
    ensure_safe_field(event.first, "event first field");
    std::string line = std::to_string(sequence) + "|" + event_name(event.kind) + "|" + event.first;
    switch (event.kind) {
        case EventKind::FailIncrement:
        case EventKind::FailReset:
        case EventKind::SessionClose:
            break;
        case EventKind::TokenConsume:
            ensure_safe_field(event.second, "event second field");
            line += "|" + event.second;
            break;
        case EventKind::SessionOpen:
        case EventKind::AuthDenied:
            ensure_safe_field(event.second, "event second field");
            ensure_safe_field(event.third, "event third field");
            line += "|" + event.second + "|" + event.third;
            break;
    }
    return line;
}

std::pair<std::uint64_t, Event> decode_event(std::string_view line) {
    const auto parts = split(line, '|');
    if (parts.size() < 3) {
        throw std::runtime_error("malformed journal event");
    }
    const auto sequence = parse_sequence(parts[0]);
    Event event;
    if (parts[1] == "fail_increment" && parts.size() == 3) {
        event = {EventKind::FailIncrement, parts[2], {}, {}};
    } else if (parts[1] == "fail_reset" && parts.size() == 3) {
        event = {EventKind::FailReset, parts[2], {}, {}};
    } else if (parts[1] == "token_consume" && parts.size() == 4) {
        event = {EventKind::TokenConsume, parts[2], parts[3], {}};
    } else if (parts[1] == "session_open" && parts.size() == 5) {
        event = {EventKind::SessionOpen, parts[2], parts[3], parts[4]};
    } else if (parts[1] == "session_close" && parts.size() == 3) {
        event = {EventKind::SessionClose, parts[2], {}, {}};
    } else if (parts[1] == "auth_denied" && parts.size() == 5) {
        event = {EventKind::AuthDenied, parts[2], parts[3], parts[4]};
    } else {
        throw std::runtime_error("unknown or malformed journal event");
    }
    return {sequence, event};
}

}  // namespace pam_lab
