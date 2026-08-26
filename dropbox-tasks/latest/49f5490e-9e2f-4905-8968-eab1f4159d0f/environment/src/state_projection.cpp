#include "pam_lab/state.hpp"

#include "pam_lab/io.hpp"

#include <algorithm>
#include <sstream>
#include <stdexcept>

namespace pam_lab {
namespace {

std::string bool_string(bool value) {
    return value ? "true" : "false";
}

void save_journal(const std::filesystem::path& root, const StateData& state) {
    std::vector<std::string> lines;
    lines.reserve(state.journal.size());
    for (const auto& record : state.journal) {
        lines.push_back(encode_event(record.sequence, record.event));
    }
    write_lines_atomic(root / "state/journal.log", lines);
}

}  // namespace

void apply_event(StateData& state, const Event& event, std::uint64_t sequence) {
    switch (event.kind) {
        case EventKind::FailIncrement: {
            auto found = state.failures.find(event.first);
            if (found == state.failures.end()) {
                throw std::runtime_error("fail increment references unknown user: " + event.first);
            }
            ++found->second.failures;
            found->second.locked = found->second.failures >= 3;
            return;
        }
        case EventKind::FailReset: {
            auto found = state.failures.find(event.first);
            if (found == state.failures.end()) {
                throw std::runtime_error("fail reset references unknown user: " + event.first);
            }
            found->second.failures = 0;
            found->second.locked = false;
            return;
        }
        case EventKind::TokenConsume: {
            auto found = state.tokens.find(event.first);
            if (found == state.tokens.end() || found->second.user != event.second) {
                throw std::runtime_error("token consume references an invalid token identity");
            }
            if (found->second.consumed) {
                throw std::runtime_error("token already consumed: " + event.first);
            }
            found->second.consumed = true;
            found->second.consumed_sequence = sequence;
            return;
        }
        case EventKind::SessionOpen: {
            if (!state.users.contains(event.second)) {
                throw std::runtime_error("session open references unknown user: " + event.second);
            }
            const auto method = parse_method(event.third);
            if (!method) {
                throw std::runtime_error("session open has invalid method");
            }
            const auto existing = state.sessions.find(event.first);
            if (existing != state.sessions.end() && existing->second.open) {
                throw std::runtime_error("session identifier is already open: " + event.first);
            }
            SessionRecord session{event.first, event.second, *method, true, sequence, 0};
            state.sessions[event.first] = session;
            state.audit.push_back(AuditRecord{sequence, "login", event.second, event.first, event.third, "allowed"});
            return;
        }
        case EventKind::SessionClose: {
            auto found = state.sessions.find(event.first);
            if (found == state.sessions.end() || !found->second.open) {
                throw std::runtime_error("session close references a non-open session: " + event.first);
            }
            found->second.open = false;
            found->second.close_sequence = sequence;
            state.audit.push_back(AuditRecord{
                sequence,
                "logout",
                found->second.user,
                found->second.id,
                to_string(found->second.method),
                "closed"});
            return;
        }
        case EventKind::AuthDenied: {
            if (!state.users.contains(event.first)) {
                throw std::runtime_error("auth denial references unknown user: " + event.first);
            }
            if (!parse_method(event.second)) {
                throw std::runtime_error("auth denial has invalid method");
            }
            state.audit.push_back(AuditRecord{
                sequence,
                "denied",
                event.first,
                "-",
                event.second,
                event.third});
            return;
        }
    }
    throw std::runtime_error("unknown event kind");
}

void save_projections(const std::filesystem::path& root, const StateData& state) {
    const auto state_directory = root / "state";
    std::filesystem::create_directories(state_directory);

    std::vector<std::string> failure_lines;
    for (const auto& [user, record] : state.failures) {
        failure_lines.push_back(user + "|" + std::to_string(record.failures) + "|" + bool_string(record.locked));
    }
    write_lines_atomic(state_directory / "faillock.db", failure_lines);

    std::vector<std::string> token_lines;
    for (const auto& [id, token] : state.tokens) {
        token_lines.push_back(
            id + "|" + token.user + "|" + token.secret + "|" +
            (token.consumed ? "consumed" : "fresh") + "|" + std::to_string(token.consumed_sequence));
    }
    write_lines_atomic(state_directory / "tokens.db", token_lines);

    std::vector<std::string> session_lines;
    for (const auto& [id, session] : state.sessions) {
        session_lines.push_back(
            id + "|" + session.user + "|" + to_string(session.method) + "|" + bool_string(session.open) + "|" +
            std::to_string(session.open_sequence) + "|" + std::to_string(session.close_sequence) + "|v1");
    }
    write_lines_atomic(state_directory / "sessions.db", session_lines);

    std::vector<AuditRecord> sorted_audit = state.audit;
    std::sort(sorted_audit.begin(), sorted_audit.end(), [](const AuditRecord& left, const AuditRecord& right) {
        return left.sequence < right.sequence;
    });
    std::vector<std::string> audit_lines;
    for (const auto& record : sorted_audit) {
        audit_lines.push_back(
            std::to_string(record.sequence) + "|" + record.kind + "|" + record.user + "|" + record.session + "|" +
            record.method + "|" + record.reason + "|v1");
    }
    write_lines_atomic(state_directory / "audit.log", audit_lines);
}

void commit_events(
    const std::filesystem::path& root,
    StateData& state,
    const std::vector<Event>& events) {
    for (const auto& event : events) {
        const auto sequence = state.next_sequence++;
        apply_event(state, event, sequence);
        if (event.durable()) {
            state.journal.push_back(JournalRecord{sequence, event});
        }
    }
    save_journal(root, state);
    save_projections(root, state);
}

void rebuild_state(const std::filesystem::path& root) {
    const auto current = load_state(root);
    const auto journal = current.journal;

    bootstrap_state(root);
    auto rebuilt = load_state(root);
    rebuilt.journal = journal;
    for (const auto& record : journal) {
        apply_event(rebuilt, record.event, record.sequence);
        rebuilt.next_sequence = std::max(rebuilt.next_sequence, record.sequence + 1);
    }
    save_projections(root, rebuilt);
    save_journal(root, rebuilt);
}

std::string snapshot_user(const std::filesystem::path& root, const std::string& user) {
    const auto state = load_state(root);
    if (!state.users.contains(user)) {
        throw std::runtime_error("unknown user: " + user);
    }
    std::ostringstream output;
    output << "user=" << user << '\n';
    const auto failure = state.failures.at(user);
    output << "failures=" << failure.failures << '\n';
    output << "locked=" << bool_string(failure.locked) << '\n';

    for (const auto& [id, token] : state.tokens) {
        if (token.user == user) {
            output << "token." << id << '=' << (token.consumed ? "consumed" : "fresh") << '\n';
        }
    }
    for (const auto& [id, session] : state.sessions) {
        if (session.user == user) {
            output << "session." << id << '=' << (session.open ? "open" : "closed") << ':' << to_string(session.method) << '\n';
        }
    }

    std::uint64_t login_count = 0;
    std::uint64_t logout_count = 0;
    std::uint64_t denied_count = 0;
    for (const auto& record : state.audit) {
        if (record.user != user) {
            continue;
        }
        if (record.kind == "login") {
            ++login_count;
        } else if (record.kind == "logout") {
            ++logout_count;
        } else if (record.kind == "denied") {
            ++denied_count;
        }
    }
    output << "audit.login=" << login_count << '\n';
    output << "audit.logout=" << logout_count << '\n';
    output << "audit.denied=" << denied_count << '\n';
    return output.str();
}

}  // namespace pam_lab
