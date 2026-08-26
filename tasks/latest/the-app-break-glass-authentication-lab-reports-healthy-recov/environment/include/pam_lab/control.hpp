#pragma once

#include "pam_lab/types.hpp"

#include <cstddef>
#include <map>
#include <string>
#include <string_view>

namespace pam_lab {

enum class ActionKind {
    Ignore,
    Bad,
    Die,
    Ok,
    Done,
    Reset,
    Jump,
};

struct Action {
    ActionKind kind{ActionKind::Bad};
    std::size_t jump{0};
};

struct ControlMap {
    std::map<PamCode, Action> explicit_actions;
    Action fallback{};

    [[nodiscard]] Action resolve(PamCode code) const;
};

Action parse_runtime_action(std::string_view value);
std::string encode_runtime_action(const Action& action);

}  // namespace pam_lab
