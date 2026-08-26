#include "pam_lab/types.hpp"

#include <stdexcept>

namespace pam_lab {

std::string to_string(PamCode code) {
    switch (code) {
        case PamCode::Success:
            return "success";
        case PamCode::AuthErr:
            return "auth_err";
        case PamCode::Ignore:
            return "ignore";
        case PamCode::MaxTries:
            return "maxtries";
        case PamCode::UserUnknown:
            return "user_unknown";
        case PamCode::SessionErr:
            return "session_err";
    }
    throw std::runtime_error("unknown PAM code");
}

std::optional<PamCode> parse_pam_code(std::string_view value) {
    if (value == "success") {
        return PamCode::Success;
    }
    if (value == "auth_err") {
        return PamCode::AuthErr;
    }
    if (value == "ignore") {
        return PamCode::Ignore;
    }
    if (value == "maxtries") {
        return PamCode::MaxTries;
    }
    if (value == "user_unknown") {
        return PamCode::UserUnknown;
    }
    if (value == "session_err") {
        return PamCode::SessionErr;
    }
    return std::nullopt;
}

std::string to_string(Method method) {
    switch (method) {
        case Method::Password:
            return "password";
        case Method::Recovery:
            return "recovery";
    }
    throw std::runtime_error("unknown method");
}

std::optional<Method> parse_method(std::string_view value) {
    if (value == "password") {
        return Method::Password;
    }
    if (value == "recovery") {
        return Method::Recovery;
    }
    return std::nullopt;
}

}  // namespace pam_lab
