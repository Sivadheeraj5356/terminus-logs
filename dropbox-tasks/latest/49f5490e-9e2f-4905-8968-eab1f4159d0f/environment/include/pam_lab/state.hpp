#pragma once

#include "pam_lab/event.hpp"
#include "pam_lab/types.hpp"

#include <cstdint>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace pam_lab {

struct UserRecord {
    std::string password;
    PamCode recovery_password_result{PamCode::AuthErr};
};

struct TokenRecord {
    std::string id;
    std::string user;
    std::string secret;
    bool consumed{false};
    std::uint64_t consumed_sequence{0};
};

struct FailRecord {
    std::uint64_t failures{0};
    bool locked{false};
};

struct SessionRecord {
    std::string id;
    std::string user;
    Method method{Method::Password};
    bool open{true};
    std::uint64_t open_sequence{0};
    std::uint64_t close_sequence{0};
};

struct AuditRecord {
    std::uint64_t sequence{0};
    std::string kind;
    std::string user;
    std::string session;
    std::string method;
    std::string reason;
};

struct JournalRecord {
    std::uint64_t sequence{0};
    Event event;
};

struct StateData {
    std::map<std::string, UserRecord> users;
    std::map<std::string, TokenRecord> tokens;
    std::map<std::string, FailRecord> failures;
    std::map<std::string, SessionRecord> sessions;
    std::vector<AuditRecord> audit;
    std::vector<JournalRecord> journal;
    std::uint64_t next_sequence{1};
};

StateData load_state(const std::filesystem::path& root);
void bootstrap_state(const std::filesystem::path& root);
void commit_events(
    const std::filesystem::path& root,
    StateData& state,
    const std::vector<Event>& events);
void rebuild_state(const std::filesystem::path& root);
std::string snapshot_user(const std::filesystem::path& root, const std::string& user);
void apply_event(StateData& state, const Event& event, std::uint64_t sequence);
void save_projections(const std::filesystem::path& root, const StateData& state);

}  // namespace pam_lab
