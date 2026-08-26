#pragma once

#include "pam_lab/control.hpp"

#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace pam_lab {

enum class TargetKind {
    Module,
    Substack,
};

struct RawEntry {
    TargetKind kind{TargetKind::Module};
    std::string target;
    std::map<std::string, std::string> controls;
};

struct RawStack {
    std::string name;
    std::vector<RawEntry> entries;
};

struct RuntimeEntry {
    TargetKind kind{TargetKind::Module};
    std::string target;
    ControlMap controls;
};

struct PolicySet {
    std::map<std::string, std::vector<RuntimeEntry>> stacks;
};

RawStack parse_raw_stack_file(const std::filesystem::path& path, bool allow_continue);
PolicySet load_runtime_policy(const std::filesystem::path& directory);
void compile_policy_directory(
    const std::filesystem::path& source_directory,
    const std::filesystem::path& output_directory);

}  // namespace pam_lab
