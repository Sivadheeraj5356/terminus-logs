#pragma once

#include <optional>
#include <string>
#include <string_view>

namespace pam_lab {

enum class PamCode {
    Success,
    AuthErr,
    Ignore,
    MaxTries,
    UserUnknown,
    SessionErr,
};

enum class Method {
    Password,
    Recovery,
};

enum class EffectPhase {
    Attempt,
    Success,
};

std::string to_string(PamCode code);
std::optional<PamCode> parse_pam_code(std::string_view value);
std::string to_string(Method method);
std::optional<Method> parse_method(std::string_view value);

}  // namespace pam_lab
