#include "staging_io.h"
#include "hash.h"
#include <cstdio>
#include <fstream>
#include <sstream>

static const char* REPAIR_RESET_PATH = "/app/state/repair-snapshot-reset.token";

static std::string trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && (s[a] == ' ' || s[a] == '\n' || s[a] == '\r' || s[a] == '\t')) ++a;
    while (b > a && (s[b - 1] == ' ' || s[b - 1] == '\n' || s[b - 1] == '\r' || s[b - 1] == '\t')) --b;
    return s.substr(a, b - a);
}

static std::vector<uint16_t> parse_u16_array(const std::string& blob, const char* key) {
    std::vector<uint16_t> vals;
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
        vals.push_back(static_cast<uint16_t>(std::stoi(tok)));
    }
    return vals;
}

static std::vector<int> parse_int_array_blob(const std::string& blob, const char* key) {
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

static bool parse_int_field(const std::string& blob, const char* key, int def, int& out) {
    std::string pat = std::string("\"") + key + "\"";
    auto pos = blob.find(pat);
    if (pos == std::string::npos) {
        out = def;
        return true;
    }
    pos = blob.find(':', pos);
    if (pos == std::string::npos) return false;
    auto val = trim(blob.substr(pos + 1));
    size_t end = 0;
    try {
        out = std::stoi(val, &end);
    } catch (...) {
        return false;
    }
    return end > 0;
}

static bool parse_u16_field(const std::string& blob, const char* key, uint16_t def, uint16_t& out) {
    int tmp = def;
    if (!parse_int_field(blob, key, def, tmp)) return false;
    out = static_cast<uint16_t>(tmp);
    return true;
}

static bool parse_bool_field(const std::string& blob, const char* key, bool def, bool& out) {
    std::string pat = std::string("\"") + key + "\"";
    auto pos = blob.find(pat);
    if (pos == std::string::npos) {
        out = def;
        return true;
    }
    pos = blob.find(':', pos);
    if (pos == std::string::npos) return false;
    auto val = trim(blob.substr(pos + 1));
    if (val.rfind("true", 0) == 0) {
        out = true;
        return true;
    }
    if (val.rfind("false", 0) == 0) {
        out = false;
        return true;
    }
    return false;
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

std::string catalog_digest_hex(const std::vector<Fragment>& fragments) {
    std::ostringstream sig;
    for (const auto& f : fragments) {
        sig << f.id << ":" << f.seq << ":" << f.partition_id << ";";
    }
    return fingerprint_hex(sig.str());
}

static void append_snapshot_json(std::ostringstream& os, const StagingSnapshot& snap) {
    os << "{\n";
    os << "  \"version\": " << snap.version << ",\n";
    os << "  \"catalog_path\": \"" << snap.catalog_path << "\",\n";
    os << "  \"open_fragment_id\": " << snap.open_fragment_id << ",\n";
    os << "  \"chain_fragment_ids\": [";
    for (size_t i = 0; i < snap.chain_fragment_ids.size(); ++i) {
        if (i) os << ", ";
        os << snap.chain_fragment_ids[i];
    }
    os << "],\n";
    os << "  \"chain_overlaps\": [";
    for (size_t i = 0; i < snap.chain_overlaps.size(); ++i) {
        if (i) os << ", ";
        os << snap.chain_overlaps[i];
    }
    os << "],\n";
    os << "  \"replica_summary\": " << (snap.replica_summary ? "true" : "false") << ",\n";
    os << "  \"catalog_digest\": \"" << snap.catalog_digest << "\"\n";
    os << "}\n";
}

bool staging_snapshot_matches_catalog(const StagingSnapshot& snap, const std::vector<Fragment>& fragments) {
    return snap.catalog_digest == catalog_digest_hex(fragments);
}

void note_repair_snapshot_reset(const std::vector<Fragment>& fragments) {
    std::ofstream out(REPAIR_RESET_PATH);
    if (out) {
        out << catalog_digest_hex(fragments) << "\n";
    }
}

bool repair_snapshot_reset_pending(const std::vector<Fragment>& fragments) {
    std::ifstream in(REPAIR_RESET_PATH);
    if (!in) return false;
    std::string token;
    std::getline(in, token);
    token = trim(token);
    if (token.empty() || token != catalog_digest_hex(fragments)) {
        return false;
    }
    std::remove(REPAIR_RESET_PATH);
    return true;
}

bool write_staging_snapshot(const std::string& path, const StagingSnapshot& snap, std::string& err) {
    std::ostringstream os;
    append_snapshot_json(os, snap);
    std::ofstream out(path);
    if (!out) {
        err = "IO_ERROR";
        return false;
    }
    out << os.str();
    return true;
}

bool read_staging_snapshot(const std::string& path, StagingSnapshot& out, std::string& err) {
    std::ifstream in(path);
    if (!in) {
        err = "STAGING_ERROR";
        return false;
    }
    std::string blob((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    int version = 0;
    if (!parse_int_field(blob, "version", 0, version) || version != 1) {
        err = "STAGING_ERROR";
        return false;
    }
    out.version = version;
    out.catalog_path = parse_string_field(blob, "catalog_path");
    if (!parse_u16_field(blob, "open_fragment_id", 0, out.open_fragment_id)) {
        err = "STAGING_ERROR";
        return false;
    }
    out.chain_fragment_ids = parse_u16_array(blob, "chain_fragment_ids");
    out.chain_overlaps = parse_int_array_blob(blob, "chain_overlaps");
    if (!parse_bool_field(blob, "replica_summary", false, out.replica_summary)) {
        err = "STAGING_ERROR";
        return false;
    }
    out.catalog_digest = parse_string_field(blob, "catalog_digest");
    if (out.chain_fragment_ids.empty() || out.catalog_digest.empty()) {
        err = "STAGING_ERROR";
        return false;
    }
    return true;
}
