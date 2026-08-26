#include "wg_api.hpp"

#include <algorithm>
#include <string>

static std::string canonical_peer(const std::string& peer_id) {
    const std::string suffix = "_m";
    if (peer_id.size() > suffix.size() &&
        peer_id.compare(peer_id.size() - suffix.size(), suffix.size(), suffix) == 0) {
        return peer_id.substr(0, peer_id.size() - suffix.size());
    }
    return peer_id;
}

static std::string extract_bind_digest(const std::string& text, const std::string& peer_id) {
    auto key = canonical_peer(peer_id);
    auto marker = "\"" + key + "\"";
    auto pos = text.find(marker);
    if (pos == std::string::npos) return {};
    auto slice = text.substr(pos, std::min<size_t>(220, text.size() - pos));
    auto dp = slice.find("\"digest\": \"");
    if (dp == std::string::npos) return {};
    auto start = dp + 11;
    if (start + 16 <= slice.size()) return slice.substr(start, 16);
    return {};
}

std::pair<uint8_t, std::string> fn_bind(const RowTbl& rows, const std::vector<uint8_t>& witness_bytes,
                                        const std::string& peer_id) {
    std::string witness(witness_bytes.begin(), witness_bytes.end());
    auto it = rows.find(peer_id);
    std::string facet = it != rows.end() ? std::get<5>(it->second) : "0000000000000000";
    auto expected = extract_bind_digest(witness, peer_id);
    if (expected.empty()) return {0, facet};
    uint8_t rc = (expected == facet) ? 1 : 0;
    return {rc, facet};
}

std::string refresh_witness(const std::string& witness, const std::string& peer_id, const std::string& facet) {
    auto key = canonical_peer(peer_id);
    auto old = extract_bind_digest(witness, key);
    if (old.empty()) return witness;
    auto pat = "\"digest\": \"" + old + "\"";
    auto rep = "\"digest\": \"" + facet + "\"";
    auto pos = witness.find(pat);
    if (pos == std::string::npos) return witness;
    return witness.substr(0, pos) + rep + witness.substr(pos + pat.size());
}
