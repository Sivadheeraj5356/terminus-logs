#include "pam_lab/policy.hpp"

#include "pam_lab/io.hpp"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace pam_lab {
namespace {

std::vector<std::string> words(const std::string& line) {
    std::istringstream stream(line);
    std::vector<std::string> values;
    std::string value;
    while (stream >> value) {
        values.push_back(value);
    }
    return values;
}

void validate_action_token(const std::string& token, bool allow_continue) {
    if (token == "ignore" || token == "bad" || token == "die" || token == "ok" ||
        token == "done" || token == "reset" || (allow_continue && token == "continue")) {
        return;
    }
    if (!token.empty() &&
        std::all_of(token.begin(), token.end(), [](unsigned char value) { return std::isdigit(value) != 0; })) {
        return;
    }
    throw std::runtime_error("unsupported policy action: " + token);
}

ControlMap to_runtime_control_map(const RawEntry& raw) {
    ControlMap controls;
    const auto fallback = raw.controls.find("default");
    if (fallback == raw.controls.end()) {
        throw std::runtime_error("runtime entry is missing default action");
    }
    controls.fallback = parse_runtime_action(fallback->second);
    for (const auto& [code_name, action_name] : raw.controls) {
        if (code_name == "default") {
            continue;
        }
        const auto code = parse_pam_code(code_name);
        if (!code) {
            throw std::runtime_error("unsupported policy return code: " + code_name);
        }
        controls.explicit_actions[*code] = parse_runtime_action(action_name);
    }
    return controls;
}

}  // namespace

RawStack parse_raw_stack_file(const std::filesystem::path& path, bool allow_continue) {
    const auto lines = read_lines(path);
    RawStack stack;
    bool started = false;
    bool ended = false;

    for (std::size_t index = 0; index < lines.size(); ++index) {
        const auto line = trim(lines[index]);
        if (line.empty() || line.front() == '#') {
            continue;
        }
        const auto tokens = words(line);
        if (!started) {
            if (tokens.size() != 2 || tokens[0] != "stack") {
                throw std::runtime_error(path.string() + ": first declaration must be 'stack <name>'");
            }
            stack.name = tokens[1];
            ensure_safe_field(stack.name, "stack name");
            started = true;
            continue;
        }
        if (tokens.size() == 1 && tokens[0] == "end") {
            ended = true;
            break;
        }
        if (tokens.size() < 4 || (tokens[0] != "module" && tokens[0] != "substack")) {
            throw std::runtime_error(path.string() + ": malformed entry on line " + std::to_string(index + 1));
        }
        RawEntry entry;
        entry.kind = tokens[0] == "module" ? TargetKind::Module : TargetKind::Substack;
        entry.target = tokens[1];
        ensure_safe_field(entry.target, "entry target");
        for (std::size_t token_index = 2; token_index < tokens.size(); ++token_index) {
            const auto& control = tokens[token_index];
            const auto equals = control.find('=');
            if (equals == std::string::npos || equals == 0 || equals + 1 == control.size()) {
                throw std::runtime_error(path.string() + ": malformed control token: " + control);
            }
            const auto key = control.substr(0, equals);
            const auto value = control.substr(equals + 1);
            if (key != "default" && !parse_pam_code(key)) {
                throw std::runtime_error(path.string() + ": unsupported return code: " + key);
            }
            validate_action_token(value, allow_continue);
            if (!entry.controls.emplace(key, value).second) {
                throw std::runtime_error(path.string() + ": duplicate control key: " + key);
            }
        }
        if (!entry.controls.contains("default")) {
            throw std::runtime_error(path.string() + ": entry is missing default control");
        }
        stack.entries.push_back(std::move(entry));
    }

    if (!started || !ended || stack.entries.empty()) {
        throw std::runtime_error(path.string() + ": incomplete stack definition");
    }
    return stack;
}

PolicySet load_runtime_policy(const std::filesystem::path& directory) {
    if (!std::filesystem::is_directory(directory)) {
        throw std::runtime_error("runtime policy directory is missing: " + directory.string());
    }
    std::vector<std::filesystem::path> files;
    for (const auto& entry : std::filesystem::directory_iterator(directory)) {
        if (entry.is_regular_file() && entry.path().extension() == ".conf") {
            files.push_back(entry.path());
        }
    }
    std::sort(files.begin(), files.end());

    PolicySet policy;
    for (const auto& file : files) {
        const auto raw = parse_raw_stack_file(file, false);
        std::vector<RuntimeEntry> entries;
        entries.reserve(raw.entries.size());
        for (const auto& entry : raw.entries) {
            entries.push_back(RuntimeEntry{entry.kind, entry.target, to_runtime_control_map(entry)});
        }
        if (!policy.stacks.emplace(raw.name, std::move(entries)).second) {
            throw std::runtime_error("duplicate runtime stack: " + raw.name);
        }
    }
    if (!policy.stacks.contains("login")) {
        throw std::runtime_error("runtime policy has no login stack");
    }
    return policy;
}

}  // namespace pam_lab
