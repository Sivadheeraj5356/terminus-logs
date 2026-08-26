#pragma once

#include "pam_lab/event.hpp"
#include "pam_lab/state.hpp"
#include "pam_lab/types.hpp"

#include <string>
#include <vector>

namespace pam_lab {

struct AuthContext {
    std::string user;
    Method method{Method::Password};
    std::string secret;
    std::string session_id;
};

struct Effect {
    EffectPhase phase{EffectPhase::Attempt};
    Event event;
};

struct ModuleResult {
    PamCode code{PamCode::AuthErr};
    std::vector<Effect> effects;
};

ModuleResult run_module(
    const std::string& module_name,
    const AuthContext& context,
    const StateData& state);

}  // namespace pam_lab
