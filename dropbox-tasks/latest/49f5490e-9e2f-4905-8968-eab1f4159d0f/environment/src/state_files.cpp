#include "pam_lab/state.hpp"

#include "pam_lab/io.hpp"

#include <algorithm>
#include <charconv>
#include <stdexcept>

namespace pam_lab {
namespace {

std::uint64_t parse_u64(const std::string& value, const std::string& field) {
    std::uint64_t parsed = 0;
    const auto result = std::from_chars(value.data(), value.data() + value.size(), parsed);
    if (result.ec != std::errc{} || result.ptr != value.data() + value.size()) {
        throw std::runtime_error("invalid integer in " + field + ": " + value);
    }
    return parsed;
}

bool parse_bool(const std::string& value, const std::string& field) {
    if (value == "true") {
        return true;
    }
    if (value == "false") {
        return false;
    }
    throw std::runtime_error("invalid boolean in " + field + ": " + value);
}

StateData load_fixtures(const std::filesystem::path& root) {
    StateData state;
    for (const auto& line : read_lines(root / "fixtures/users.db")) {
        if (trim(line).empty()) {
            continue;
        }
        const auto parts = split(line, '|');
        if (parts.size() != 3) {
            throw std::runtime_error("malformed users fixture row");
        }
        const auto result = parse_pam_code(parts[2]);
        if (!result || (*result != PamCode::AuthErr && *result != PamCode::Ignore)) {
            throw std::runtime_error("unsupported password non-applicable result: " + parts[2]);
        }
        ensure_safe_field(parts[0], "user name");
        ensure_safe_field(parts[1], "password");
        if (!state.users.emplace(parts[0], UserRecord{parts[1], *result}).second) {
            throw std::runtime_error("duplicate user fixture: " + parts[0]);
        }
        state.failures.emplace(parts[0], FailRecord{});
    }
    if (state.users.empty()) {
        throw std::runtime_error("users fixture is empty");
    }

    for (const auto& line : read_lines(root / "fixtures/tokens.db")) {
        if (trim(line).empty()) {
            continue;
        }
        const auto parts = split(line, '|');
        if (parts.size() != 3) {
            throw std::runtime_error("malformed tokens fixture row");
        }
        ensure_safe_field(parts[0], "token id");
        ensure_safe_field(parts[1], "token user");
        ensure_safe_field(parts[2], "token secret");
        if (!state.users.contains(parts[1])) {
            throw std::runtime_error("token references unknown user: " + parts[1]);
        }
        TokenRecord token{parts[0], parts[1], parts[2], false, 0};
        if (!state.tokens.emplace(parts[0], std::move(token)).second) {
            throw std::runtime_error("duplicate token fixture: " + parts[0]);
        }
    }
    return state;
}

void load_failures(const std::filesystem::path& path, StateData& state) {
    state.failures.clear();
    for (const auto& line : read_lines(path)) {
        if (trim(line).empty()) {
            continue;
        }
        const auto parts = split(line, '|');
        if (parts.size() != 3 || !state.users.contains(parts[0])) {
            throw std::runtime_error("malformed faillock state row");
        }
        state.failures[parts[0]] = FailRecord{parse_u64(parts[1], "faillock"), parse_bool(parts[2], "faillock")};
    }
    for (const auto& [user, ignored] : state.users) {
        static_cast<void>(ignored);
        if (!state.failures.contains(user)) {
            throw std::runtime_error("faillock state is missing user: " + user);
        }
    }
}

void load_tokens(const std::filesystem::path& path, StateData& state) {
    std::map<std::string, TokenRecord> loaded;
    for (const auto& line : read_lines(path)) {
        if (trim(line).empty()) {
            continue;
        }
        const auto parts = split(line, '|');
        if (parts.size() != 5) {
            throw std::runtime_error("malformed token state row");
        }
        const bool consumed = parts[3] == "consumed";
        if (!consumed && parts[3] != "fresh") {
            throw std::runtime_error("invalid token state");
        }
        TokenRecord token{parts[0], parts[1], parts[2], consumed, parse_u64(parts[4], "token state")};
        loaded.emplace(token.id, std::move(token));
    }
    if (loaded.size() != state.tokens.size()) {
        throw std::runtime_error("token projection does not match fixtures");
    }
    for (const auto& [id, fixture] : state.tokens) {
        const auto found = loaded.find(id);
        if (found == loaded.end() || found->second.user != fixture.user || found->second.secret != fixture.secret) {
            throw std::runtime_error("token projection identity mismatch: " + id);
        }
    }
    state.tokens = std::move(loaded);
}

void load_sessions(const std::filesystem::path& path, StateData& state) {
    state.sessions.clear();
    for (const auto& line : read_lines(path)) {
        if (trim(line).empty()) {
            continue;
        }
        const auto parts = split(line, '|');
        if (parts.size() != 7) {
            throw std::runtime_error("malformed session state row");
        }
        const auto method = parse_method(parts[2]);
        if (!method) {
            throw std::runtime_error("invalid session method");
        }
        SessionRecord session{
            parts[0],
            parts[1],
            *method,
            parse_bool(parts[3], "session state"),
            parse_u64(parts[4], "session open sequence"),
            parse_u64(parts[5], "session close sequence")};
        if (parts[6] != "v1") {
            throw std::runtime_error("unsupported session state version");
        }
        state.sessions.emplace(session.id, std::move(session));
    }
}

void load_audit(const std::filesystem::path& path, StateData& state) {
    state.audit.clear();
    for (const auto& line : read_lines(path)) {
        if (trim(line).empty()) {
            continue;
        }
        const auto parts = split(line, '|');
        if (parts.size() != 7) {
            throw std::runtime_error("malformed audit row");
        }
        AuditRecord record{
            parse_u64(parts[0], "audit sequence"),
            parts[1],
            parts[2],
            parts[3],
            parts[4],
            parts[5]};
        if (parts[6] != "v1") {
            throw std::runtime_error("unsupported audit version");
        }
        state.audit.push_back(std::move(record));
    }
}

void load_journal(const std::filesystem::path& path, StateData& state) {
    state.journal.clear();
    for (const auto& line : read_lines(path)) {
        if (trim(line).empty()) {
            continue;
        }
        auto [sequence, event] = decode_event(line);
        state.journal.push_back(JournalRecord{sequence, std::move(event)});
    }
    std::sort(state.journal.begin(), state.journal.end(), [](const JournalRecord& left, const JournalRecord& right) {
        return left.sequence < right.sequence;
    });
    for (std::size_t index = 1; index < state.journal.size(); ++index) {
        if (state.journal[index - 1].sequence >= state.journal[index].sequence) {
            throw std::runtime_error("journal sequence is not strictly increasing");
        }
    }
}

std::uint64_t calculate_next_sequence(const StateData& state) {
    std::uint64_t maximum = 0;
    for (const auto& record : state.journal) {
        maximum = std::max(maximum, record.sequence);
    }
    for (const auto& record : state.audit) {
        maximum = std::max(maximum, record.sequence);
    }
    for (const auto& [ignored, token] : state.tokens) {
        static_cast<void>(ignored);
        maximum = std::max(maximum, token.consumed_sequence);
    }
    for (const auto& [ignored, session] : state.sessions) {
        static_cast<void>(ignored);
        maximum = std::max(maximum, session.open_sequence);
        maximum = std::max(maximum, session.close_sequence);
    }
    return maximum + 1;
}

}  // namespace

StateData load_state(const std::filesystem::path& root) {
    StateData state = load_fixtures(root);
    const auto state_directory = root / "state";
    load_failures(state_directory / "faillock.db", state);
    load_tokens(state_directory / "tokens.db", state);
    load_sessions(state_directory / "sessions.db", state);
    load_audit(state_directory / "audit.log", state);
    load_journal(state_directory / "journal.log", state);
    state.next_sequence = calculate_next_sequence(state);
    return state;
}

void bootstrap_state(const std::filesystem::path& root) {
    if (!std::filesystem::is_directory(root / "pam.d")) {
        throw std::runtime_error("lab root is missing pam.d");
    }
    StateData state = load_fixtures(root);
    state.next_sequence = 1;
    std::filesystem::create_directories(root / "state");
    save_projections(root, state);
    write_lines_atomic(root / "state/journal.log", {});
}

}  // namespace pam_lab
