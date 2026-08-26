#pragma once

#include "pam_lab/modules.hpp"
#include "pam_lab/policy.hpp"

#include <string>
#include <vector>

namespace pam_lab {

struct Evaluation {
    PamCode code{PamCode::Ignore};
    std::vector<Effect> effects;
};

class StackEngine {
  public:
    StackEngine(const PolicySet& policy, const StateData& state);

    Evaluation evaluate(const std::string& stack_name, const AuthContext& context) const;

  private:
    Evaluation evaluate_internal(
        const std::string& stack_name,
        const AuthContext& context,
        std::size_t depth) const;

    const PolicySet& policy_;
    const StateData& state_;
};

}  // namespace pam_lab
