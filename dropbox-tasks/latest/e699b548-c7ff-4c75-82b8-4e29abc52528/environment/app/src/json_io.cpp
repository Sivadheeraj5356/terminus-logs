#include "json_io.h"
#include <fstream>
#include <sstream>

static std::string trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && (s[a] == ' ' || s[a] == '\n' || s[a] == '\r' || s[a] == '\t')) ++a;
    while (b > a && (s[b-1] == ' ' || s[b-1] == '\n' || s[b-1] == '\r' || s[b-1] == '\t')) --b;
    return s.substr(a, b - a);
}

static bool parse_bool(const std::string& blob, const char* key, bool def, bool& out) {
    std::string pat = std::string("\"") + key + "\"";
    auto pos = blob.find(pat);
    if (pos == std::string::npos) { out = def; return true; }
    pos = blob.find(':', pos);
    if (pos == std::string::npos) return false;
    auto val = trim(blob.substr(pos + 1));
    if (val.rfind("true", 0) == 0) { out = true; return true; }
    if (val.rfind("false", 0) == 0) { out = false; return true; }
    return false;
}

static bool parse_int(const std::string& blob, const char* key, int def, int& out) {
    std::string pat = std::string("\"") + key + "\"";
    auto pos = blob.find(pat);
    if (pos == std::string::npos) { out = def; return true; }
    pos = blob.find(':', pos);
    if (pos == std::string::npos) return false;
    auto val = trim(blob.substr(pos + 1));
    size_t end = 0;
    try { out = std::stoi(val, &end); } catch (...) { return false; }
    return end > 0;
}

static bool parse_u16_field(const std::string& blob, const char* key, uint16_t def, uint16_t& out) {
    int tmp = def;
    if (!parse_int(blob, key, def, tmp)) return false;
    out = static_cast<uint16_t>(tmp);
    return true;
}

static bool parse_u32_field(const std::string& blob, const char* key, uint32_t def, uint32_t& out) {
    int tmp = def;
    if (!parse_int(blob, key, static_cast<int>(def), tmp)) return false;
    out = static_cast<uint32_t>(tmp);
    return true;
}

static bool parse_u64_field(const std::string& blob, const char* key, uint64_t def, uint64_t& out) {
    std::string pat = std::string("\"") + key + "\"";
    auto pos = blob.find(pat);
    if (pos == std::string::npos) { out = def; return true; }
    pos = blob.find(':', pos);
    if (pos == std::string::npos) return false;
    auto val = trim(blob.substr(pos + 1));
    try { out = std::stoull(val); } catch (...) { return false; }
    return true;
}

bool read_policy_file(const std::string& path, Policy& out, std::string& err) {
    std::ifstream in(path);
    if (!in) { err = "POLICY_ERROR"; return false; }
    std::string blob((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    if (!parse_int(blob, "min_row_overlap", 3, out.min_row_overlap)) { err = "POLICY_ERROR"; return false; }
    if (!parse_bool(blob, "case_fold_ascii", true, out.case_fold_ascii)) { err = "POLICY_ERROR"; return false; }
    if (!parse_int(blob, "max_ambiguity", 0, out.max_ambiguity)) { err = "POLICY_ERROR"; return false; }
  if (!parse_u16_field(blob, "required_replica_mask", 0x0007, out.required_replica_mask)) { err = "POLICY_ERROR"; return false; }
    if (!parse_int(blob, "scan_cost_per_byte", 1, out.scan_cost_per_byte)) { err = "POLICY_ERROR"; return false; }
    if (!parse_int(blob, "scan_penalty_per_gap", 10, out.scan_penalty_per_gap)) { err = "POLICY_ERROR"; return false; }
    return true;
}

static std::vector<uint16_t> parse_id_array(const std::string& blob) {
    std::vector<uint16_t> ids;
    auto pos = blob.find("\"fragment_ids\"");
    if (pos == std::string::npos) return ids;
    pos = blob.find('[', pos);
    auto end = blob.find(']', pos);
    if (pos == std::string::npos || end == std::string::npos) return ids;
    std::string inner = blob.substr(pos + 1, end - pos - 1);
    std::stringstream ss(inner);
    std::string tok;
    while (std::getline(ss, tok, ',')) {
        tok = trim(tok);
        if (tok.empty()) continue;
        ids.push_back(static_cast<uint16_t>(std::stoi(tok)));
    }
    return ids;
}

static std::vector<int> parse_int_array(const std::string& blob, const char* key) {
    std::vector<int> vals;
    std::string pat = std::string("\"") + key + "\"";
    auto pos = blob.find(pat);
    if (pos == std::string::npos) return vals;
    pos = blob.find('[', pos);
    auto end = blob.find(']', pos);
    if (pos == std::string::npos || end == std::string::npos) return vals;
    std::string inner = blob.substr(pos + 1, end - pos - 1);
    std::stringstream ss(inner);
    std::string tok;
    while (std::getline(ss, tok, ',')) {
        tok = trim(tok);
        if (tok.empty()) continue;
        vals.push_back(std::stoi(tok));
    }
    return vals;
}

static std::string parse_string_field(const std::string& blob, const char* key) {
    std::string pat = std::string("\"") + key + "\"";
    auto pos = blob.find(pat);
    if (pos == std::string::npos) return "";
    pos = blob.find(':', pos);
    if (pos == std::string::npos) return "";
    pos = blob.find('"', pos);
    if (pos == std::string::npos) return "";
    ++pos;
    std::string out;
    while (pos < blob.size() && blob[pos] != '"') {
        if (blob[pos] == '\\' && pos + 1 < blob.size()) {
            out.push_back(blob[pos + 1]);
            pos += 2;
        } else {
            out.push_back(blob[pos]);
            ++pos;
        }
    }
    return out;
}

bool read_plan_file(const std::string& path, CompactionPlan& out, std::string& err) {
    std::ifstream in(path);
    if (!in) { err = "PLAN_ERROR"; return false; }
    std::string blob((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    out.fragment_ids = parse_id_array(blob);
    out.row_overlap_lengths = parse_int_array(blob, "row_overlap_lengths");
    if (!parse_u32_field(blob, "total_rows", 0, out.total_rows)) { err = "PLAN_ERROR"; return false; }
    if (!parse_u64_field(blob, "scan_cost_units", 0, out.scan_cost_units)) { err = "PLAN_ERROR"; return false; }
    if (!parse_u32_field(blob, "fragmentation_index", 0, out.fragmentation_index)) { err = "PLAN_ERROR"; return false; }
    if (!parse_bool(blob, "replica_consistent", false, out.replica_consistent)) { err = "PLAN_ERROR"; return false; }
    out.fingerprint = parse_string_field(blob, "fingerprint");
    if (out.fragment_ids.empty() || out.fingerprint.empty()) { err = "PLAN_ERROR"; return false; }
    return true;
}

bool write_text_file(const std::string& path, const std::string& content, std::string& err) {
    std::ofstream out(path);
    if (!out) { err = "IO_ERROR"; return false; }
    out << content;
    return true;
}
