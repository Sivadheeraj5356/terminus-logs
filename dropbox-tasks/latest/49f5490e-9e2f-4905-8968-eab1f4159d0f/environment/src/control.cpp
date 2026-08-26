#include "pam_lab/control.hpp"

#include <charconv>
#include <stdexcept>

namespace pam_lab {

Action ControlMap::resolve(PamCode code) const {
    const auto found = explicit_actions.find(code);
    return found == explicit_actions.end() ? fallback : found->second;
}

Action parse_runtime_action(std::string_view value) {
    if (value == "ignore") {
        return {ActionKind::Ignore, 0};
    }
    if (value == "bad") {
        return {ActionKind::Bad, 0};
    }
    if (value == "die") {
        return {ActionKind::Die, 0};
    }
    if (value == "ok") {
        return {ActionKind::Ok, 0};
    }
    if (value == "done") {
        return {ActionKind::Done, 0};
    }
    if (value == "reset") {
        return {ActionKind::Reset, 0};
    }

    std::size_t jump = 0;
    const auto* begin = value.data();
    const auto* end = value.data() + value.size();
    const auto result = std::from_chars(begin, end, jump);
    if (result.ec == std::errc{} && result.ptr == end) {
        return {ActionKind::Jump, jump};
    }
    throw std::runtime_error("unknown runtime action: " + std::string(value));
}

std::string encode_runtime_action(const Action& action) {
    switch (action.kind) {
        case ActionKind::Ignore:
            return "ignore";
        case ActionKind::Bad:
            return "bad";
        case ActionKind::Die:
            return "die";
        case ActionKind::Ok:
            return "ok";
        case ActionKind::Done:
            return "done";
        case ActionKind::Reset:
            return "reset";
        case ActionKind::Jump:
            return std::to_string(action.jump);
    }
    throw std::runtime_error("unknown control action");
}

}  // namespace pam_lab
