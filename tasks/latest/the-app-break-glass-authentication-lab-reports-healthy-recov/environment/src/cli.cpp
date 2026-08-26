#include "pam_lab/cli.hpp"

#include <iostream>
#include <stdexcept>

namespace pam_lab {

std::map<std::string, std::string> parse_flags(int argc, char** argv, int start_index) {
    std::map<std::string, std::string> flags;
    for (int index = start_index; index < argc; index += 2) {
        if (index + 1 >= argc) {
            throw std::runtime_error("missing value for flag: " + std::string(argv[index]));
        }
        const std::string name = argv[index];
        if (!name.starts_with("--")) {
            throw std::runtime_error("expected flag, got: " + name);
        }
        if (!flags.emplace(name, argv[index + 1]).second) {
            throw std::runtime_error("duplicate flag: " + name);
        }
    }
    return flags;
}

std::string require_flag(
    const std::map<std::string, std::string>& flags,
    const std::string& name) {
    const auto found = flags.find(name);
    if (found == flags.end() || found->second.empty()) {
        throw std::runtime_error("missing required flag: " + name);
    }
    return found->second;
}

void print_authctl_usage() {
    std::cerr
        << "usage:\n"
        << "  authctl bootstrap --root PATH\n"
        << "  authctl login --root PATH --user USER --method password|recovery --secret SECRET --session ID\n"
        << "  authctl logout --root PATH --session ID\n"
        << "  authctl snapshot --root PATH --user USER\n"
        << "  authctl rebuild --root PATH\n"
        << "  authctl checkpoint --root PATH --label LABEL\n"
        << "  authctl restore --root PATH --label LABEL\n"
        << "  authctl probe-recovery --root PATH --user USER --secret SECRET\n";
}

void print_policyc_usage() {
    std::cerr << "usage: policyc --source PATH --output PATH\n";
}

}  // namespace pam_lab
