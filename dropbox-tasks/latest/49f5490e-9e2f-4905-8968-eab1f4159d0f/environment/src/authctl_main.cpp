#include "pam_lab/cli.hpp"
#include "pam_lab/checkpoint.hpp"
#include "pam_lab/service.hpp"
#include "pam_lab/state.hpp"
#include "pam_lab/types.hpp"

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    using namespace pam_lab;
    try {
        if (argc < 2) {
            print_authctl_usage();
            return 64;
        }
        const std::string command = argv[1];
        const auto flags = parse_flags(argc, argv, 2);
        const std::filesystem::path root = require_flag(flags, "--root");

        if (command == "bootstrap") {
            bootstrap_state(root);
            std::cout << "BOOTSTRAPPED root=" << root.string() << '\n';
            return 0;
        }
        if (command == "login") {
            const auto method = parse_method(require_flag(flags, "--method"));
            if (!method) {
                throw std::runtime_error("method must be password or recovery");
            }
            AuthContext context{
                require_flag(flags, "--user"),
                *method,
                require_flag(flags, "--secret"),
                require_flag(flags, "--session")};
            const auto result = login(root, context);
            if (result.allowed) {
                std::cout << "ALLOWED user=" << context.user << " method=" << to_string(context.method)
                          << " session=" << context.session_id << '\n';
                return 0;
            }
            std::cout << "DENIED user=" << context.user << " method=" << to_string(context.method)
                      << " code=" << to_string(result.code) << '\n';
            return 2;
        }
        if (command == "logout") {
            const auto session = require_flag(flags, "--session");
            if (!logout(root, session)) {
                std::cout << "NOT_OPEN session=" << session << '\n';
                return 3;
            }
            std::cout << "CLOSED session=" << session << '\n';
            return 0;
        }
        if (command == "snapshot") {
            std::cout << snapshot_user(root, require_flag(flags, "--user"));
            return 0;
        }
        if (command == "rebuild") {
            rebuild_state(root);
            std::cout << "REBUILT root=" << root.string() << '\n';
            return 0;
        }
        if (command == "checkpoint") {
            const auto label = require_flag(flags, "--label");
            save_checkpoint(root, label);
            std::cout << "CHECKPOINT label=" << label << '\n';
            return 0;
        }
        if (command == "restore") {
            const auto label = require_flag(flags, "--label");
            restore_checkpoint(root, label);
            std::cout << "RESTORED label=" << label << '\n';
            return 0;
        }
        if (command == "probe-recovery") {
            const auto result = probe_recovery(
                root,
                require_flag(flags, "--user"),
                require_flag(flags, "--secret"));
            std::cout << "PROBE code=" << to_string(result.code) << " effects=" << result.effects.size() << '\n';
            return result.code == PamCode::Success ? 0 : 4;
        }

        print_authctl_usage();
        return 64;
    } catch (const std::exception& error) {
        std::cerr << "authctl: " << error.what() << '\n';
        return 70;
    }
}
