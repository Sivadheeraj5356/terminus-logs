#include <algorithm>
#include <cstdint>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

using i64 = std::int64_t;
using u64 = std::uint64_t;

struct Wave {
    int index = 0;
    i64 change_minutes = 0;
    i64 audit_minutes = 0;
    i64 compromised_exposure_multiplier = 0;
    i64 pending_attestation_multiplier = 0;
};

struct Service {
    std::string id;
    std::string owner;
    std::string domain;
    i64 hsm_rotation_minutes = 0;
    i64 software_rotation_minutes = 0;
    i64 attestation_minutes = 0;
    i64 compromised_exposure_weight = 0;
    i64 hsm_pending_weight = 0;
    i64 software_pending_weight = 0;
    i64 hsm_escrow_mb = 0;
    i64 software_escrow_mb = 0;
};

struct DualTrust {
    int provider = -1;
    i64 enable_minutes = 0;
    i64 disable_minutes = 0;
    i64 storage_mb = 0;
    i64 carrying_cost = 0;
};

struct Case {
    int wave_count = 0;
    int max_actions = 0;
    int max_software_rotations = 0;
    i64 max_dual_trust_mb = 0;
    i64 max_escrow_mb = 0;
    std::vector<Wave> waves;
    std::vector<Service> services;
    std::vector<std::pair<int, int>> mtls_edges;
    std::vector<DualTrust> dual_trusts;
    std::vector<int> dual_trust_for_service;
};

static std::vector<std::string> split(const std::string& line) {
    std::istringstream input(line);
    std::vector<std::string> fields;
    std::string field;
    while (input >> field) {
        fields.push_back(field);
    }
    return fields;
}

static i64 number(const std::string& value) {
    std::size_t used = 0;
    i64 parsed = std::stoll(value, &used);
    if (used != value.size() || parsed < 0) {
        throw std::runtime_error("invalid non-negative integer: " + value);
    }
    return parsed;
}

static Case parse_case(const std::string& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open input: " + path);
    }

    Case result;
    std::vector<std::vector<std::string>> raw_mtls_edges;
    std::vector<std::vector<std::string>> raw_dual_trusts;
    std::unordered_map<std::string, int> service_index;
    std::string raw;
    while (std::getline(input, raw)) {
        auto first = raw.find_first_not_of(" \t\r\n");
        if (first == std::string::npos || raw[first] == '#') {
            continue;
        }
        auto fields = split(raw);
        if (fields[0] == "PARAM" && fields.size() == 3) {
            i64 value = number(fields[2]);
            if (fields[1] == "wave_count") result.wave_count = static_cast<int>(value);
            else if (fields[1] == "max_actions_per_wave") result.max_actions = static_cast<int>(value);
            else if (fields[1] == "max_software_rotations") result.max_software_rotations = static_cast<int>(value);
            else if (fields[1] == "max_dual_trust_mb") result.max_dual_trust_mb = value;
            else if (fields[1] == "max_escrow_mb") result.max_escrow_mb = value;
            else throw std::runtime_error("unknown PARAM: " + fields[1]);
        } else if (fields[0] == "WAVE" && fields.size() == 6) {
            result.waves.push_back({static_cast<int>(number(fields[1])), number(fields[2]), number(fields[3]),
                number(fields[4]), number(fields[5])});
        } else if (fields[0] == "SERVICE" && fields.size() == 12) {
            if (service_index.count(fields[1])) throw std::runtime_error("duplicate service: " + fields[1]);
            int index = static_cast<int>(result.services.size());
            service_index[fields[1]] = index;
            result.services.push_back({fields[1], fields[2], fields[3], number(fields[4]), number(fields[5]),
                number(fields[6]), number(fields[7]), number(fields[8]), number(fields[9]), number(fields[10]),
                number(fields[11])});
        } else if (fields[0] == "MTLS" && fields.size() == 3) {
            raw_mtls_edges.push_back(fields);
        } else if (fields[0] == "DUAL_TRUST" && fields.size() == 6) {
            raw_dual_trusts.push_back(fields);
        } else {
            throw std::runtime_error("invalid row: " + raw);
        }
    }

    if (result.wave_count <= 0 || result.max_actions <= 0 || result.max_software_rotations < 0
        || result.max_dual_trust_mb <= 0 || result.max_escrow_mb <= 0) {
        throw std::runtime_error("missing or invalid PARAM rows");
    }
    if (result.services.empty() || result.services.size() > 63 || raw_dual_trusts.size() > 63) {
        throw std::runtime_error("unsupported service or dual_trust count");
    }
    if (static_cast<int>(result.waves.size()) != result.wave_count) {
        throw std::runtime_error("wrong WAVE count");
    }
    for (int i = 0; i < result.wave_count; ++i) {
        if (result.waves[i].index != i + 1) throw std::runtime_error("WAVE rows out of order");
    }

    for (const auto& row : raw_mtls_edges) {
        if (!service_index.count(row[1]) || !service_index.count(row[2])) {
            throw std::runtime_error("MTLS names unknown service");
        }
        result.mtls_edges.emplace_back(service_index[row[1]], service_index[row[2]]);
    }
    result.dual_trust_for_service.assign(result.services.size(), -1);
    for (const auto& row : raw_dual_trusts) {
        auto found = service_index.find(row[1]);
        if (found == service_index.end()) throw std::runtime_error("DUAL_TRUST names unknown service");
        int provider = found->second;
        if (result.dual_trust_for_service[provider] != -1) throw std::runtime_error("duplicate DUAL_TRUST provider");
        int dual_trust_index = static_cast<int>(result.dual_trusts.size());
        result.dual_trust_for_service[provider] = dual_trust_index;
        result.dual_trusts.push_back({provider, number(row[2]), number(row[3]), number(row[4]), number(row[5])});
    }
    return result;
}

enum class ActionType { RotateHsm, RotateSoftware, Attest, DualTrustOn, DualTrustOff };

struct Action {
    ActionType type;
    int service = -1;
    int dual_trust = -1;
    std::string id;
    i64 minutes = 0;
};

struct State {
    int wave = 0;
    u64 rotated = 0;
    u64 software = 0;
    u64 attested = 0;
    u64 active = 0;
    u64 used = 0;

    bool operator==(const State& other) const {
        return wave == other.wave && rotated == other.rotated && software == other.software && attested == other.attested
            && active == other.active && used == other.used;
    }
};

struct StateHash {
    std::size_t operator()(const State& state) const {
        std::size_t h = std::hash<u64>{}(state.rotated);
        h ^= std::hash<u64>{}(state.software + 0x13198a2e03707344ULL + (h << 6) + (h >> 2));
        h ^= std::hash<u64>{}(state.attested + 0x243f6a8885a308d3ULL + (h << 6) + (h >> 2));
        h ^= std::hash<u64>{}(state.active + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2));
        h ^= std::hash<u64>{}(state.used + 0x517cc1b727220a95ULL + (h << 6) + (h >> 2));
        h ^= std::hash<int>{}(state.wave + 0x45d9f3b + static_cast<int>(h));
        return h;
    }
};

struct Result {
    bool feasible = false;
    i64 credential_exposure_units = 0;
    i64 peak_dual_trust_mb = 0;
    i64 peak_escrow_mb = 0;
    i64 response_minutes = 0;
    std::vector<std::vector<std::string>> schedule;
};

static bool better(const Result& left, const Result& right) {
    if (!left.feasible) return false;
    if (!right.feasible) return true;
    if (left.credential_exposure_units != right.credential_exposure_units) return left.credential_exposure_units < right.credential_exposure_units;
    if (left.peak_dual_trust_mb != right.peak_dual_trust_mb) return left.peak_dual_trust_mb < right.peak_dual_trust_mb;
    if (left.peak_escrow_mb != right.peak_escrow_mb) return left.peak_escrow_mb < right.peak_escrow_mb;
    if (left.response_minutes != right.response_minutes) return left.response_minutes < right.response_minutes;
    return left.schedule < right.schedule;
}

class Optimizer {
public:
    explicit Optimizer(Case input) : data(std::move(input)) {
        all_rotated = data.services.size() == 64 ? ~u64{0} : ((u64{1} << data.services.size()) - 1);
    }

    Result solve() {
        Result answer = visit({0, 0, 0, 0, 0, 0});
        if (!answer.feasible) throw std::runtime_error("input has no feasible credential rotation schedule");
        return answer;
    }

private:
    Case data;
    u64 all_rotated = 0;
    std::unordered_map<State, Result, StateHash> memo;

    i64 dual_trust_storage(u64 active) const {
        i64 total = 0;
        for (std::size_t i = 0; i < data.dual_trusts.size(); ++i) {
            if (active & (u64{1} << i)) total += data.dual_trusts[i].storage_mb;
        }
        return total;
    }

    i64 escrow_storage(u64 rotated, u64 software, u64 attested) const {
        i64 total = 0;
        for (std::size_t i = 0; i < data.services.size(); ++i) {
            u64 bit = u64{1} << i;
            if ((rotated & bit) && !(attested & bit)) {
                total += (software & bit) ? data.services[i].software_escrow_mb : data.services[i].hsm_escrow_mb;
            }
        }
        return total;
    }

    i64 wave_cost(int wave, u64 rotated, u64 software, u64 attested, u64 active) const {
        i64 total = 0;
        for (std::size_t i = 0; i < data.services.size(); ++i) {
            if (!(rotated & (u64{1} << i))) {
                total += data.waves[wave].compromised_exposure_multiplier * data.services[i].compromised_exposure_weight;
            } else if (!(attested & (u64{1} << i))) {
                total += data.waves[wave].pending_attestation_multiplier
                    * ((software & (u64{1} << i)) ? data.services[i].software_pending_weight
                                               : data.services[i].hsm_pending_weight);
            }
        }
        for (std::size_t i = 0; i < data.dual_trusts.size(); ++i) {
            if (active & (u64{1} << i)) total += data.dual_trusts[i].carrying_cost;
        }
        return total;
    }

    bool compatible(u64 rotated, u64 active) const {
        for (auto [consumer, provider] : data.mtls_edges) {
            bool consumer_new = (rotated & (u64{1} << consumer)) != 0;
            bool provider_new = (rotated & (u64{1} << provider)) != 0;
            if (consumer_new == provider_new) continue;
            int dual_trust = data.dual_trust_for_service[provider];
            if (dual_trust < 0 || !(active & (u64{1} << dual_trust))) return false;
        }
        return true;
    }

    bool attestation_dependencies(u64 attested) const {
        for (auto [consumer, provider] : data.mtls_edges) {
            if ((attested & (u64{1} << consumer)) && !(attested & (u64{1} << provider))) return false;
        }
        return true;
    }

    bool capacity_lower_bound(const State& state) const {
        int waves_left = data.wave_count - state.wave;
        int required_actions = static_cast<int>(data.services.size()) - __builtin_popcountll(state.rotated)
            + static_cast<int>(data.services.size()) - __builtin_popcountll(state.attested)
            + __builtin_popcountll(state.active);
        if (required_actions > waves_left * data.max_actions) return false;

        i64 required_change = 0;
        i64 required_audit = 0;
        for (std::size_t i = 0; i < data.services.size(); ++i) {
            if (!(state.rotated & (u64{1} << i))) {
                required_change += std::min(data.services[i].hsm_rotation_minutes,
                    data.services[i].software_rotation_minutes);
            }
            if (!(state.attested & (u64{1} << i))) required_audit += data.services[i].attestation_minutes;
        }
        for (std::size_t i = 0; i < data.dual_trusts.size(); ++i) {
            if (state.active & (u64{1} << i)) required_change += data.dual_trusts[i].disable_minutes;
        }
        i64 available_change = 0;
        i64 available_audit = 0;
        for (int i = state.wave; i < data.wave_count; ++i) {
            available_change += data.waves[i].change_minutes;
            available_audit += data.waves[i].audit_minutes;
        }
        return required_change <= available_change && required_audit <= available_audit;
    }

    std::vector<Action> available(const State& state) const {
        std::vector<Action> actions;
        for (std::size_t i = 0; i < data.services.size(); ++i) {
            if (!(state.rotated & (u64{1} << i))) {
                actions.push_back({ActionType::RotateSoftware, static_cast<int>(i), -1,
                    "ROTATE_SOFTWARE_" + data.services[i].id, data.services[i].software_rotation_minutes});
                actions.push_back({ActionType::RotateHsm, static_cast<int>(i), -1,
                    "ROTATE_HSM_" + data.services[i].id, data.services[i].hsm_rotation_minutes});
            } else if (!(state.attested & (u64{1} << i))) {
                actions.push_back({ActionType::Attest, static_cast<int>(i), -1,
                    "ATTEST_" + data.services[i].id, data.services[i].attestation_minutes});
            }
        }
        for (std::size_t i = 0; i < data.dual_trusts.size(); ++i) {
            const auto& dual_trust = data.dual_trusts[i];
            const std::string& provider = data.services[dual_trust.provider].id;
            if (state.active & (u64{1} << i)) {
                actions.push_back({ActionType::DualTrustOff, dual_trust.provider, static_cast<int>(i),
                    "DUAL_TRUST_OFF_" + provider, dual_trust.disable_minutes});
            } else if (!(state.used & (u64{1} << i))) {
                actions.push_back({ActionType::DualTrustOn, dual_trust.provider, static_cast<int>(i),
                    "DUAL_TRUST_ON_" + provider, dual_trust.enable_minutes});
            }
        }
        std::sort(actions.begin(), actions.end(), [](const Action& a, const Action& b) { return a.id < b.id; });
        return actions;
    }

    Result visit(const State& state) {
        auto known = memo.find(state);
        if (known != memo.end()) return known->second;

        if (state.wave == data.wave_count) {
            Result terminal;
            terminal.feasible = state.rotated == all_rotated && state.attested == all_rotated && state.active == 0;
            memo.emplace(state, terminal);
            return terminal;
        }
        if (!capacity_lower_bound(state)) {
            Result impossible;
            memo.emplace(state, impossible);
            return impossible;
        }

        const auto actions = available(state);
        std::vector<int> chosen;
        Result best;

        auto evaluate = [&]() {
            i64 change_minutes = 0;
            i64 audit_minutes = 0;
            u64 rotated = state.rotated;
            u64 software = state.software;
            u64 attested = state.attested;
            u64 active = state.active;
            u64 used = state.used;
            std::vector<std::string> ids;
            std::vector<std::string> domains;

            for (int selected : chosen) {
                const Action& action = actions[selected];
                ids.push_back(action.id);
                if (action.type == ActionType::RotateHsm || action.type == ActionType::RotateSoftware
                    || action.type == ActionType::Attest) {
                    const std::string& domain = data.services[action.service].domain;
                    if (std::find(domains.begin(), domains.end(), domain) != domains.end()) return;
                    domains.push_back(domain);
                    if (action.type == ActionType::RotateHsm || action.type == ActionType::RotateSoftware) {
                        change_minutes += action.minutes;
                        rotated |= u64{1} << action.service;
                        if (action.type == ActionType::RotateSoftware) software |= u64{1} << action.service;
                    } else {
                        audit_minutes += action.minutes;
                        attested |= u64{1} << action.service;
                    }
                } else if (action.type == ActionType::DualTrustOn) {
                    change_minutes += action.minutes;
                    active |= u64{1} << action.dual_trust;
                    used |= u64{1} << action.dual_trust;
                } else {
                    change_minutes += action.minutes;
                    active &= ~(u64{1} << action.dual_trust);
                }
            }
            if (change_minutes > data.waves[state.wave].change_minutes
                || audit_minutes > data.waves[state.wave].audit_minutes) return;
            i64 dual_trust_mb = dual_trust_storage(active);
            i64 escrow_mb = escrow_storage(rotated, software, attested);
            if (__builtin_popcountll(software) > data.max_software_rotations
                || dual_trust_mb > data.max_dual_trust_mb || escrow_mb > data.max_escrow_mb
                || !compatible(rotated, active) || !attestation_dependencies(attested)) return;

            State next{state.wave + 1, rotated, software, attested, active, used};
            if (!capacity_lower_bound(next)) return;
            Result suffix = visit(next);
            if (!suffix.feasible) return;

            Result candidate;
            candidate.feasible = true;
            candidate.credential_exposure_units = wave_cost(state.wave, rotated, software, attested, active) + suffix.credential_exposure_units;
            candidate.peak_dual_trust_mb = std::max(dual_trust_mb, suffix.peak_dual_trust_mb);
            candidate.peak_escrow_mb = std::max(escrow_mb, suffix.peak_escrow_mb);
            candidate.response_minutes = change_minutes + audit_minutes + suffix.response_minutes;
            candidate.schedule.reserve(1 + suffix.schedule.size());
            candidate.schedule.push_back(std::move(ids));
            candidate.schedule.insert(candidate.schedule.end(), suffix.schedule.begin(), suffix.schedule.end());
            if (better(candidate, best)) best = std::move(candidate);
        };

        std::function<void(int)> enumerate = [&](int start) {
            evaluate();
            if (static_cast<int>(chosen.size()) == data.max_actions) return;
            for (int i = start; i < static_cast<int>(actions.size()); ++i) {
                chosen.push_back(i);
                enumerate(i + 1);
                chosen.pop_back();
            }
        };
        enumerate(0);
        memo.emplace(state, best);
        return best;
    }
};

static std::string json_string(const std::string& value) {
    std::string result = "\"";
    for (unsigned char ch : value) {
        if (ch == '\\' || ch == '"') {
            result.push_back('\\');
            result.push_back(static_cast<char>(ch));
        } else if (ch == '\n') result += "\\n";
        else if (ch == '\r') result += "\\r";
        else if (ch == '\t') result += "\\t";
        else result.push_back(static_cast<char>(ch));
    }
    result.push_back('"');
    return result;
}

static void json_array(std::ostream& out, const std::vector<std::string>& values) {
    out << '[';
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i) out << ',';
        out << json_string(values[i]);
    }
    out << ']';
}

static void solve_file(const std::string& input_path, const std::string& output_path) {
    Case data = parse_case(input_path);
    Result answer = Optimizer(data).solve();

    std::unordered_map<std::string, Action> action_by_id;
    for (std::size_t i = 0; i < data.services.size(); ++i) {
        Action hsm{ActionType::RotateHsm, static_cast<int>(i), -1,
            "ROTATE_HSM_" + data.services[i].id, data.services[i].hsm_rotation_minutes};
        Action software{ActionType::RotateSoftware, static_cast<int>(i), -1,
            "ROTATE_SOFTWARE_" + data.services[i].id, data.services[i].software_rotation_minutes};
        Action attest{ActionType::Attest, static_cast<int>(i), -1,
            "ATTEST_" + data.services[i].id, data.services[i].attestation_minutes};
        action_by_id.emplace(hsm.id, hsm);
        action_by_id.emplace(software.id, software);
        action_by_id.emplace(attest.id, attest);
    }
    for (std::size_t i = 0; i < data.dual_trusts.size(); ++i) {
        const auto& dual_trust = data.dual_trusts[i];
        const auto& provider = data.services[dual_trust.provider].id;
        Action on{ActionType::DualTrustOn, dual_trust.provider, static_cast<int>(i),
            "DUAL_TRUST_ON_" + provider, dual_trust.enable_minutes};
        Action off{ActionType::DualTrustOff, dual_trust.provider, static_cast<int>(i),
            "DUAL_TRUST_OFF_" + provider, dual_trust.disable_minutes};
        action_by_id.emplace(on.id, on);
        action_by_id.emplace(off.id, off);
    }

    std::ofstream out(output_path);
    if (!out) throw std::runtime_error("cannot open output: " + output_path);
    out << "{\n";
    out << "  \"credential_exposure_units\": " << answer.credential_exposure_units << ",\n";
    out << "  \"peak_dual_trust_mb\": " << answer.peak_dual_trust_mb << ",\n";
    out << "  \"peak_escrow_mb\": " << answer.peak_escrow_mb << ",\n";
    out << "  \"total_response_minutes\": " << answer.response_minutes << ",\n";
    out << "  \"waves\": [\n";

    u64 rotated = 0;
    u64 attested = 0;
    u64 active = 0;
    for (int wave = 0; wave < data.wave_count; ++wave) {
        i64 change_minutes = 0;
        i64 audit_minutes = 0;
        for (const auto& id : answer.schedule[wave]) {
            const Action& action = action_by_id.at(id);
            if (action.type == ActionType::RotateHsm || action.type == ActionType::RotateSoftware) {
                change_minutes += action.minutes;
                rotated |= u64{1} << action.service;
            } else if (action.type == ActionType::Attest) {
                audit_minutes += action.minutes;
                attested |= u64{1} << action.service;
            } else if (action.type == ActionType::DualTrustOn) {
                change_minutes += action.minutes;
                active |= u64{1} << action.dual_trust;
            } else {
                change_minutes += action.minutes;
                active &= ~(u64{1} << action.dual_trust);
            }
        }
        std::vector<std::string> active_ids;
        std::vector<std::string> compromised_ids;
        std::vector<std::string> awaiting_ids;
        std::vector<std::string> attested_ids;
        for (std::size_t i = 0; i < data.dual_trusts.size(); ++i) {
            if (active & (u64{1} << i)) active_ids.push_back(data.services[data.dual_trusts[i].provider].id);
        }
        for (std::size_t i = 0; i < data.services.size(); ++i) {
            u64 bit = u64{1} << i;
            if (!(rotated & bit)) compromised_ids.push_back(data.services[i].id);
            else if (!(attested & bit)) awaiting_ids.push_back(data.services[i].id);
            else attested_ids.push_back(data.services[i].id);
        }
        std::sort(active_ids.begin(), active_ids.end());
        std::sort(compromised_ids.begin(), compromised_ids.end());
        std::sort(awaiting_ids.begin(), awaiting_ids.end());
        std::sort(attested_ids.begin(), attested_ids.end());
        out << "    {\"wave_index\": " << wave + 1 << ", \"action_ids\": ";
        json_array(out, answer.schedule[wave]);
        out << ", \"change_minutes\": " << change_minutes << ", \"audit_minutes\": " << audit_minutes
            << ", \"active_dual_trust_service_ids\": ";
        json_array(out, active_ids);
        out << ", \"remaining_compromised_service_ids\": ";
        json_array(out, compromised_ids);
        out << ", \"awaiting_attestation_service_ids\": ";
        json_array(out, awaiting_ids);
        out << ", \"attested_service_ids\": ";
        json_array(out, attested_ids);
        out << '}';
        if (wave + 1 != data.wave_count) out << ',';
        out << '\n';
    }
    out << "  ]\n}\n";
}
