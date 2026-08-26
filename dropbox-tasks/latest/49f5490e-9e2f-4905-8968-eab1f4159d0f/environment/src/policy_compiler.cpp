#include "pam_lab/policy.hpp"

#include "pam_lab/io.hpp"

#include <algorithm>
#include <fstream>
#include <stdexcept>

namespace pam_lab {
namespace {

std::string lower_source_action(
    const RawEntry& entry,
    const std::string& return_code,
    const std::string& source_action) {
    if (source_action != "continue") {
        return source_action;
    }
    if (entry.kind == TargetKind::Substack && return_code == "ignore") {
        return "1";
    }
    return "ignore";
}

std::string render_entry(const RawEntry& entry) {
    std::string line = entry.kind == TargetKind::Module ? "module " : "substack ";
    line += entry.target;
    for (const auto& [return_code, action] : entry.controls) {
        if (return_code == "default") {
            continue;
        }
        line += " " + return_code + "=" + lower_source_action(entry, return_code, action);
    }
    const auto fallback = entry.controls.find("default");
    line += " default=" + lower_source_action(entry, "default", fallback->second);
    return line;
}

}  // namespace

void compile_policy_directory(
    const std::filesystem::path& source_directory,
    const std::filesystem::path& output_directory) {
    if (!std::filesystem::is_directory(source_directory)) {
        throw std::runtime_error("source policy directory is missing: " + source_directory.string());
    }
    std::vector<std::filesystem::path> files;
    for (const auto& entry : std::filesystem::directory_iterator(source_directory)) {
        if (entry.is_regular_file() && entry.path().extension() == ".policy") {
            files.push_back(entry.path());
        }
    }
    std::sort(files.begin(), files.end());
    if (files.empty()) {
        throw std::runtime_error("source policy directory has no .policy files");
    }

    std::filesystem::create_directories(output_directory);
    for (const auto& existing : std::filesystem::directory_iterator(output_directory)) {
        if (existing.is_regular_file() && existing.path().extension() == ".conf") {
            std::filesystem::remove(existing.path());
        }
    }

    for (const auto& source_file : files) {
        const auto stack = parse_raw_stack_file(source_file, true);
        std::vector<std::string> output;
        output.push_back("stack " + stack.name);
        for (const auto& entry : stack.entries) {
            output.push_back(render_entry(entry));
        }
        output.push_back("end");
        const auto destination = output_directory / (source_file.stem().string() + ".conf");
        write_lines_atomic(destination, output);
    }
}

}  // namespace pam_lab
