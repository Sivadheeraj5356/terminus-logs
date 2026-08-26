#pragma once

#include <map>
#include <string>

namespace pam_lab {

std::map<std::string, std::string> parse_flags(int argc, char** argv, int start_index);
std::string require_flag(
    const std::map<std::string, std::string>& flags,
    const std::string& name);
void print_authctl_usage();
void print_policyc_usage();

}  // namespace pam_lab
