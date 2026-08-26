#include "pam_lab/cli.hpp"
#include "pam_lab/policy.hpp"

#include <filesystem>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    using namespace pam_lab;
    try {
        const auto flags = parse_flags(argc, argv, 1);
        const std::filesystem::path source = require_flag(flags, "--source");
        const std::filesystem::path output = require_flag(flags, "--output");
        compile_policy_directory(source, output);
        std::cout << "compiled policy from " << source.string() << " to " << output.string() << '\n';
        return 0;
    } catch (const std::exception& error) {
        print_policyc_usage();
        std::cerr << "policyc: " << error.what() << '\n';
        return 70;
    }
}
