#include "pam_lab/engine.hpp"

#include <optional>
#include <stdexcept>

namespace pam_lab {

StackEngine::StackEngine(const PolicySet& policy, const StateData& state)
    : policy_(policy), state_(state) {}

Evaluation StackEngine::evaluate(const std::string& stack_name, const AuthContext& context) const {
    return evaluate_internal(stack_name, context, 0);
}

Evaluation StackEngine::evaluate_internal(
    const std::string& stack_name,
    const AuthContext& context,
    std::size_t depth) const {
    if (depth > 16) {
        throw std::runtime_error("policy substack recursion limit exceeded");
    }
    const auto stack = policy_.stacks.find(stack_name);
    if (stack == policy_.stacks.end()) {
        throw std::runtime_error("unknown policy stack: " + stack_name);
    }

    std::optional<PamCode> first_failure;
    bool any_success = false;
    std::vector<Effect> effects;

    std::size_t index = 0;
    while (index < stack->second.size()) {
        const auto& entry = stack->second[index];
        Evaluation result;
        if (entry.kind == TargetKind::Module) {
            auto module_result = run_module(entry.target, context, state_);
            result.code = module_result.code;
            result.effects = std::move(module_result.effects);
        } else {
            result = evaluate_internal(entry.target, context, depth + 1);
        }
        effects.insert(effects.end(), result.effects.begin(), result.effects.end());

        const auto action = entry.controls.resolve(result.code);
        switch (action.kind) {
            case ActionKind::Ignore:
                ++index;
                break;
            case ActionKind::Bad:
                if (!first_failure) {
                    first_failure = result.code;
                }
                ++index;
                break;
            case ActionKind::Die:
                if (!first_failure) {
                    first_failure = result.code;
                }
                return {*first_failure, effects};
            case ActionKind::Ok:
                if (result.code == PamCode::Success) {
                    any_success = true;
                } else if (!first_failure) {
                    first_failure = result.code;
                }
                ++index;
                break;
            case ActionKind::Done:
                if (!first_failure && result.code == PamCode::Success) {
                    return {PamCode::Success, effects};
                }
                ++index;
                break;
            case ActionKind::Reset:
                first_failure.reset();
                any_success = false;
                ++index;
                break;
            case ActionKind::Jump:
                index += action.jump + 1;
                break;
        }
    }

    if (first_failure) {
        return {*first_failure, effects};
    }
    return {any_success ? PamCode::Success : PamCode::Ignore, effects};
}

}  // namespace pam_lab
