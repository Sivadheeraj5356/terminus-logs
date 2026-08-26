#include "wg_api.hpp"
#include "wg_replay.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>

extern int fn_p5(const char* env_root, const char* peer_id, char* overlap_out, size_t overlap_cap);

namespace {

std::string trim(const std::string& s) {
    size_t start = 0;
    while (start < s.size() && std::isspace(static_cast<unsigned char>(s[start]))) ++start;
    size_t end = s.size();
    while (end > start && std::isspace(static_cast<unsigned char>(s[end - 1]))) --end;
    return s.substr(start, end - start);
}

std::string env_root() {
    const char* root = std::getenv("WG_ENV_ROOT");
    return root ? root : ".";
}

std::string base_peer(const std::string& peer_id) {
    const std::string suffix = "_m";
    if (peer_id.size() > suffix.size() &&
        peer_id.compare(peer_id.size() - suffix.size(), suffix.size(), suffix) == 0) {
        return peer_id.substr(0, peer_id.size() - suffix.size());
    }
    return peer_id;
}

bool local_mux_ok(const std::string& root) {
    std::ifstream tok(root + "/w8g/staged/local_mux.token");
    if (!tok) return false;
    std::string line;
    return static_cast<bool>(std::getline(tok, line)) && line == "ok";
}

}  // namespace

std::string file_digest16(const std::string& path) {
    std::ifstream in(path);
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    return wg_md5_hex16(text);
}

PermTbl load_perm_tbl(const std::string& path) {
    PermTbl out;
    std::ifstream in(path);
    std::string line;
    int32_t current = -1;
    while (std::getline(in, line)) {
        line = trim(line);
        if (line.empty() || line[0] == '#') continue;
        if (line == "[[seed]]") {
            current = -1;
            continue;
        }
        if (current < 0 && !line.empty() && std::isdigit(static_cast<unsigned char>(line[0]))) {
            current = std::stoi(line);
            out[current] = {};
            continue;
        }
        auto eq = line.find('=');
        if (eq == std::string::npos || current < 0) continue;
        auto key = trim(line.substr(0, eq));
        auto val = trim(line.substr(eq + 1));
        out[current][key] = std::stod(val);
    }
    return out;
}

OvTbl load_ov_tbl(const std::string& path) {
    OvTbl out;
    std::ifstream in(path);
    std::string line;
    while (std::getline(in, line)) {
        line = trim(line);
        if (line.empty() || line[0] == '#') continue;
        auto eq = line.find('=');
        if (eq == std::string::npos) continue;
        uint32_t id = static_cast<uint32_t>(std::stoul(trim(line.substr(0, eq))));
        auto val = trim(line.substr(eq + 1));
        if (!val.empty() && val.front() == '"') val = val.substr(1, val.size() - 2);
        out[id] = val;
    }
    return out;
}

std::string flow_digest_rows(const std::vector<PeerRow>& rows) {
    std::vector<std::string> parts;
    for (const auto& row : rows) {
        std::ostringstream oss;
        oss << row.peer_id << "|" << row.bind_hex << "|" << static_cast<int>(row.mux_rc) << "|"
            << static_cast<int>(row.mark_rc) << "|" << static_cast<int>(row.ov_rc) << "|"
            << static_cast<int>(row.seal_rc);
        parts.push_back(oss.str());
    }
    std::sort(parts.begin(), parts.end());
    std::ostringstream joined;
    for (size_t i = 0; i < parts.size(); ++i) {
        if (i) joined << "|";
        joined << parts[i];
    }
    return wg_md5_hex16(joined.str());
}

static PhaseTrace emit_row(std::vector<PeerRow>& rows, RowTbl& row_tbl, std::string& witness_text,
                           const std::string& peer_id, uint8_t mux_rc, uint8_t mark_rc, uint8_t ov_rc,
                           int32_t shift_code, const std::string& facet) {
    auto bind = fn_bind(row_tbl, std::vector<uint8_t>(witness_text.begin(), witness_text.end()), peer_id);
    uint8_t seal_rc = bind.first;
    std::string facet_out = bind.second.empty() ? facet : bind.second;
    if (!facet.empty()) facet_out = facet;
    witness_text = refresh_witness(witness_text, peer_id, facet_out);
    auto rebound = fn_bind(row_tbl, std::vector<uint8_t>(witness_text.begin(), witness_text.end()), peer_id);
    seal_rc = rebound.first;
    if (mux_rc == 1 && mark_rc == 1 && ov_rc == 1) seal_rc = 1;
    row_tbl[peer_id] = {mux_rc, mark_rc, ov_rc, seal_rc, shift_code, facet_out};
    rows.push_back({peer_id, mux_rc, mark_rc, ov_rc, seal_rc, shift_code, facet_out});
    return {"row", peer_id + ":" + facet_out};
}

std::pair<std::vector<PeerRow>, std::vector<PhaseTrace>> run_pipeline(PipelineInput& input) {
    std::vector<PeerRow> rows;
    std::vector<PhaseTrace> traces;
    RowTbl row_tbl;
    const auto root = env_root();
    const std::string perm_path = root + "/data/perm_tbl.toml";
    const std::string perm_epoch = file_digest16(perm_path);

    MuxSnapshot snap;
    int loaded = 0;

    if (input.profile == Profile::Apply && input.hook_replay && replay_load_snapshot(&snap) == 0) {
        loaded = 1;
    } else {
        uint32_t route_mark = 42;
        auto sit = input.perm_tbl->find(input.variant_seed);
        if (sit != input.perm_tbl->end()) {
            auto tit = sit->second.find("route_mark");
            if (tit != sit->second.end()) route_mark = static_cast<uint32_t>(tit->second);
        }
        capture_mux_snapshot(snap, input.variant_seed, route_mark);

        snap.perm_epoch = perm_epoch;
        if (input.profile == Profile::Stage ||
            (input.profile == Profile::Apply && input.hook_replay)) {
            replay_save_snapshot(snap);
        }
    }

    const std::string epoch = loaded ? snap.perm_epoch : perm_epoch;
    const std::string f3_mark = snap.f3_mark;
    const std::string k7_digest = snap.k7_digest;
    const int f3_rc = (f3_mark == "detached") ? 1 : 0;
    const int k7_rc = snap.k7_rc;

    traces.push_back({"epoch", epoch});
    traces.push_back({"mux", k7_digest.empty() ? "none" : k7_digest});
    traces.push_back({"mark", f3_mark});

    for (size_t idx = 0; idx < input.peer_ids->size(); ++idx) {
        const auto& peer_id = (*input.peer_ids)[idx];
        uint8_t mux_rc = (k7_rc == 1) ? 1 : 0;

        uint8_t mark_rc = 0;
        if (input.profile == Profile::Apply) {
            mark_rc = (local_mux_ok(root) && f3_rc == 1 && mux_rc == 1) ? 1 : 0;
        }

        char ov_buf[32] = {0};
        uint8_t ov_rc = fn_p5(root.c_str(), base_peer(peer_id).c_str(), ov_buf, sizeof(ov_buf)) == 1 ? 1 : 0;

        uint32_t route_mark = 42;
        auto sit = input.perm_tbl->find(input.variant_seed);
        double weight = 1.0;
        if (sit != input.perm_tbl->end()) {
            auto tit = sit->second.find("route_mark");
            if (tit != sit->second.end()) route_mark = static_cast<uint32_t>(tit->second);
            auto wit = sit->second.find(base_peer(peer_id));
            if (wit != sit->second.end()) weight += wit->second;
        }
        (void)route_mark;

        std::ostringstream mat;
        mat << base_peer(peer_id) << "|" << f3_mark << "|" << std::string(ov_buf) << "|" << std::fixed
            << std::setprecision(3) << weight << "|bx=" << epoch;
        auto facet = wg_md5_hex16(mat.str());
        int32_t shift = (mux_rc == 1 && mark_rc == 1 && ov_rc == 1) ? 0 : 2;
        traces.push_back(emit_row(rows, row_tbl, input.witness_text, peer_id, mux_rc, mark_rc, ov_rc, shift, facet));
    }

    return {rows, traces};
}
