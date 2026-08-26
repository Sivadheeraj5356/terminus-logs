#include "pam_lab/ward.hpp"

namespace pam_lab {

std::vector<Event> gather_attempt_staging(const std::vector<Effect>& effects) {
    std::vector<Event> staged;
    for (const auto& effect : effects) {
        if (effect.phase == EffectPhase::Attempt) {
            staged.push_back(effect.event);
            continue;
        }
        if (effect.event.kind == EventKind::TokenConsume) {
            staged.push_back(effect.event);
        }
    }
    return staged;
}

std::vector<Event> gather_success_staging(const std::vector<Effect>& effects) {
    std::vector<Event> staged;
    for (const auto& effect : effects) {
        if (effect.phase == EffectPhase::Success) {
            staged.push_back(effect.event);
        }
    }
    return staged;
}

}  // namespace pam_lab
