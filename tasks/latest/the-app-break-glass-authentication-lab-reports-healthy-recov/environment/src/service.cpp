#include "pam_lab/service.hpp"

#include "pam_lab/engine.hpp"
#include "pam_lab/policy.hpp"
#include "pam_lab/state.hpp"
#include "pam_lab/ward.hpp"

#include <stdexcept>
#include <vector>

namespace pam_lab {
namespace {

bool session_is_open(const StateData& state, const std::string& session_id) {
    const auto found = state.sessions.find(session_id);
    return found != state.sessions.end() && found->second.open;
}

}  // namespace

LoginResult login(const std::filesystem::path& root, const AuthContext& context) {
    if (context.user.empty() || context.secret.empty() || context.session_id.empty()) {
        throw std::runtime_error("login fields must not be empty");
    }
    auto state = load_state(root);
    const auto policy = load_runtime_policy(root / "pam.d");
    const StackEngine engine(policy, state);
    const auto evaluation = engine.evaluate("login", context);

    auto staged_attempt = gather_attempt_staging(evaluation.effects);
    if (evaluation.code != PamCode::Success) {
        staged_attempt.push_back(Event{
            EventKind::AuthDenied,
            context.user,
            to_string(context.method),
            to_string(evaluation.code)});
        commit_events(root, state, staged_attempt);
        return {false, evaluation.code, to_string(evaluation.code)};
    }

    if (session_is_open(state, context.session_id)) {
        staged_attempt.push_back(Event{
            EventKind::AuthDenied,
            context.user,
            to_string(context.method),
            to_string(PamCode::SessionErr)});
        commit_events(root, state, staged_attempt);
        return {false, PamCode::SessionErr, to_string(PamCode::SessionErr)};
    }

    auto staged_success = gather_success_staging(evaluation.effects);
    if (context.method == Method::Recovery) {
        staged_success.insert(
            staged_success.begin(),
            Event{EventKind::FailReset, context.user, {}, {}});
    }
    staged_success.push_back(Event{
        EventKind::SessionOpen,
        context.session_id,
        context.user,
        to_string(context.method)});

    staged_attempt.insert(staged_attempt.end(), staged_success.begin(), staged_success.end());
    commit_events(root, state, staged_attempt);
    return {true, PamCode::Success, "allowed"};
}

bool logout(const std::filesystem::path& root, const std::string& session_id) {
    auto state = load_state(root);
    const auto found = state.sessions.find(session_id);
    if (found == state.sessions.end() || !found->second.open) {
        return false;
    }
    commit_events(root, state, {Event{EventKind::SessionClose, session_id, {}, {}}});
    return true;
}

ModuleResult probe_recovery(
    const std::filesystem::path& root,
    const std::string& user,
    const std::string& secret) {
    const auto state = load_state(root);
    return run_module("recovery", AuthContext{user, Method::Recovery, secret, "probe"}, state);
}

}  // namespace pam_lab
