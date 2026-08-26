#pragma once

#include "pam_lab/modules.hpp"
#include "pam_lab/types.hpp"

#include <filesystem>
#include <string>

namespace pam_lab {

struct LoginResult {
    bool allowed{false};
    PamCode code{PamCode::AuthErr};
    std::string reason;
};

LoginResult login(const std::filesystem::path& root, const AuthContext& context);
bool logout(const std::filesystem::path& root, const std::string& session_id);
ModuleResult probe_recovery(
    const std::filesystem::path& root,
    const std::string& user,
    const std::string& secret);

}  // namespace pam_lab
