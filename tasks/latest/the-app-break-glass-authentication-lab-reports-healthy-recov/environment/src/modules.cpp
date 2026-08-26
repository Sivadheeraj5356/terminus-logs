#include "pam_lab/modules.hpp"

#include <stdexcept>

namespace pam_lab {
namespace {

ModuleResult run_faillock(const AuthContext& context, const StateData& state) {
    if (!state.users.contains(context.user)) {
        return {PamCode::UserUnknown, {}};
    }
    if (context.method == Method::Recovery) {
        return {PamCode::Ignore, {}};
    }
    const auto found = state.failures.find(context.user);
    if (found == state.failures.end()) {
        throw std::runtime_error("faillock projection is missing user: " + context.user);
    }
    return {found->second.locked ? PamCode::MaxTries : PamCode::Success, {}};
}

ModuleResult run_password(const AuthContext& context, const StateData& state) {
    const auto found = state.users.find(context.user);
    if (found == state.users.end()) {
        return {PamCode::UserUnknown, {}};
    }
    if (context.method == Method::Recovery) {
        return {found->second.recovery_password_result, {}};
    }
    if (context.secret == found->second.password) {
        return {
            PamCode::Success,
            {{EffectPhase::Success, Event{EventKind::FailReset, context.user, {}, {}}}}};
    }
    return {
        PamCode::AuthErr,
        {{EffectPhase::Attempt, Event{EventKind::FailIncrement, context.user, {}, {}}}}};
}

ModuleResult run_recovery(const AuthContext& context, const StateData& state) {
    if (!state.users.contains(context.user)) {
        return {PamCode::UserUnknown, {}};
    }
    if (context.method == Method::Password) {
        return {PamCode::Ignore, {}};
    }
    for (const auto& [id, token] : state.tokens) {
        if (token.user == context.user && token.secret == context.secret && !token.consumed) {
            return {
                PamCode::Success,
                {{EffectPhase::Success, Event{EventKind::TokenConsume, id, context.user, {}}}}};
        }
    }
    return {PamCode::AuthErr, {}};
}

}  // namespace

ModuleResult run_module(
    const std::string& module_name,
    const AuthContext& context,
    const StateData& state) {
    if (module_name == "faillock") {
        return run_faillock(context, state);
    }
    if (module_name == "password") {
        return run_password(context, state);
    }
    if (module_name == "recovery") {
        return run_recovery(context, state);
    }
    if (module_name == "deny") {
        return {PamCode::AuthErr, {}};
    }
    throw std::runtime_error("unknown authentication module: " + module_name);
}

}  // namespace pam_lab
