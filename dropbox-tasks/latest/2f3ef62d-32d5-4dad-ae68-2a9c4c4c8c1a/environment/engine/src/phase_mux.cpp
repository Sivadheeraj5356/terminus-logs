#include "ph_iface.hpp"
#include "vx_api.hpp"
#include "vx_types.hpp"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::string trimmed(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && (s[a] == ' ' || s[a] == '\t' || s[a] == '\r')) ++a;
    while (b > a && (s[b - 1] == ' ' || s[b - 1] == '\t' || s[b - 1] == '\r')) --b;
    return s.substr(a, b - a);
}

std::string unquote(const std::string& s) {
    std::string t = trimmed(s);
    while (!t.empty() && (t.front() == '"')) t.erase(t.begin());
    while (!t.empty() && (t.back() == '"')) t.pop_back();
    return t;
}

std::vector<std::string> load_member_ids(const std::string& root) {
    std::vector<std::string> out;
    std::ifstream in(root + "/docs/member_ids.txt");
    std::string line;
    while (std::getline(in, line)) {
        auto t = trimmed(line);
        if (!t.empty()) out.push_back(t);
    }
    return out;
}

std::map<std::string, double> load_weights(const std::string& root, int seed) {
    std::map<std::string, double> out;
    {
        std::ifstream in(root + "/data/bump_tbl.toml");
        std::string line;
        while (std::getline(in, line)) {
            auto t = trimmed(line);
            if (t.empty() || t[0] == '#' || t[0] == '[') continue;
            auto eq = t.find('=');
            if (eq == std::string::npos) continue;
            auto k = trimmed(t.substr(0, eq));
            auto v = trimmed(t.substr(eq + 1));
            try {
                out[k] = std::stod(v);
            } catch (...) {
            }
        }
    }
    std::string shift;
    {
        std::ifstream in(root + "/data/perm_tbl.toml");
        std::string line;
        int cur = -1;
        while (std::getline(in, line)) {
            auto t = trimmed(line);
            if (t.rfind("seed", 0) == 0) {
                auto eq = t.find('=');
                if (eq != std::string::npos) {
                    try {
                        cur = std::stoi(trimmed(t.substr(eq + 1)));
                    } catch (...) {
                    }
                }
            }
            if (t.rfind("weight_shift", 0) == 0 && cur == seed) {
                auto eq = t.find('=');
                if (eq != std::string::npos) shift = unquote(t.substr(eq + 1));
            }
        }
    }
    if (!shift.empty()) {
        out[shift] += 0.250;
        std::string echo = shift + "_echo";
        if (out.count(echo)) out[echo] += 0.250;
    }
    return out;
}

std::string load_triple(const std::string& root, int seed) {
    std::ifstream in(root + "/data/rank_tbl.toml");
    std::string line;
    int cur = -1;
    std::string triple = "x86_64-linux";
    while (std::getline(in, line)) {
        auto t = trimmed(line);
        if (t.rfind("seed", 0) == 0) {
            auto eq = t.find('=');
            if (eq != std::string::npos) {
                try {
                    cur = std::stoi(trimmed(t.substr(eq + 1)));
                } catch (...) {
                }
            }
        }
        if (t.rfind("triple", 0) == 0 && cur == seed) {
            auto eq = t.find('=');
            if (eq != std::string::npos) triple = unquote(t.substr(eq + 1));
        }
    }
    return triple;
}

std::string json_escape(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c == '\\' || c == '"') out += '\\';
        out += c;
    }
    return out;
}

void append_phase(const std::string& phase, const std::string& detail) {
    std::system("mkdir -p /app/output/run_traces");
    std::ofstream out("/app/output/run_traces/phase.jsonl", std::ios::app);
    out << "{\"phase\":\"" << json_escape(phase) << "\",\"detail\":\"" << json_escape(detail)
        << "\"}\n";
}

void write_report(const std::string& path, const std::vector<Row>& rows, const Summary& sum) {
    auto slash = path.find_last_of('/');
    if (slash != std::string::npos) {
        std::string cmd = "mkdir -p " + path.substr(0, slash);
        std::system(cmd.c_str());
    }
    std::ostringstream body;
    body << "{\n  \"rows\": [\n";
    for (size_t i = 0; i < rows.size(); ++i) {
        const auto& r = rows[i];
        body << "    {\"lane_id\": \"" << json_escape(r.lane_id) << "\", \"loc_rc\": " << r.loc_rc
             << ", \"img_rc\": " << r.img_rc << ", \"bind_rc\": " << r.bind_rc
             << ", \"lag_code\": " << r.lag_code << ", \"facet_hex\": \"" << json_escape(r.facet_hex)
             << "\"}";
        if (i + 1 < rows.size()) body << ",";
        body << "\n";
    }
    body << "  ],\n  \"summary\": {\n"
         << "    \"rows_total\": " << sum.rows_total << ",\n"
         << "    \"sync_label\": \"" << sum.sync_label << "\",\n"
         << "    \"span_band\": " << sum.span_band << ",\n"
         << "    \"matrix_digest\": \"" << sum.matrix_digest << "\",\n"
         << "    \"pack_epoch\": " << sum.pack_epoch << ",\n"
         << "    \"settle_epoch\": " << sum.settle_epoch << ",\n"
         << "    \"chain_bind\": \"" << json_escape(sum.chain_bind) << "\"\n"
         << "  }\n}\n";
    std::ofstream out(path);
    out << body.str();
}

uint32_t seed_pressure_for(const std::string& lane) {
    // Deterministic fixture baseline used when no prior state exists.
    uint32_t h = 0;
    for (char c : lane) h = h * 131u + static_cast<unsigned char>(c);
    return 3u + (h % 3u);  // 3..5
}

bool read_runtime_state(const std::string& path, RuntimeState& st) {
    std::ifstream in(path);
    if (!in) return false;
    std::string body((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    auto ep = body.find("\"epoch\"");
    if (ep != std::string::npos) {
        auto colon = body.find(':', ep);
        if (colon != std::string::npos) {
            try {
                st.epoch = static_cast<uint64_t>(std::stoull(body.substr(colon + 1)));
            } catch (...) {
            }
        }
    }
    size_t pos = 0;
    while (true) {
        auto lid = body.find("\"lane_id\"", pos);
        if (lid == std::string::npos) break;
        auto q1 = body.find('"', lid + 9);
        if (q1 == std::string::npos) break;
        auto q2 = body.find('"', q1 + 1);
        if (q2 == std::string::npos) break;
        LanePressure lp;
        lp.lane_id = body.substr(q1 + 1, q2 - q1 - 1);
        auto pr = body.find("\"pending_arp_pressure\"", q2);
        if (pr != std::string::npos && pr < q2 + 200) {
            auto c2 = body.find(':', pr);
            try {
                lp.pending_arp_pressure = static_cast<uint32_t>(std::stoul(body.substr(c2 + 1)));
            } catch (...) {
            }
        }
        auto md = body.find("\"membership_digest\"", q2);
        if (md != std::string::npos && md < q2 + 300) {
            auto qq1 = body.find('"', md + 20);
            if (qq1 != std::string::npos) {
                auto qq2 = body.find('"', qq1 + 1);
                if (qq2 != std::string::npos) {
                    lp.membership_digest = body.substr(qq1 + 1, qq2 - qq1 - 1);
                }
            }
        }
        st.lanes.push_back(lp);
        pos = q2 + 1;
    }
    return true;
}

void write_runtime_state(const std::string& path, const RuntimeState& st) {
    std::system("mkdir -p /app/output");
    std::ostringstream body;
    body << "{\n  \"epoch\": " << st.epoch << ",\n  \"lanes\": [\n";
    for (size_t i = 0; i < st.lanes.size(); ++i) {
        const auto& lp = st.lanes[i];
        body << "    {\"lane_id\": \"" << json_escape(lp.lane_id)
             << "\", \"pending_arp_pressure\": " << lp.pending_arp_pressure
             << ", \"membership_digest\": \"" << json_escape(lp.membership_digest) << "\"}";
        if (i + 1 < st.lanes.size()) body << ",";
        body << "\n";
    }
    body << "  ]\n}\n";
    std::ofstream out(path);
    out << body.str();
}

struct ArpLine {
    uint64_t epoch = 0;
    std::string lane_id;
    std::string membership_digest;
    uint32_t pending_after_decay = 0;
};

void write_arp_journal(const std::string& path, const std::vector<ArpLine>& lines) {
    std::system("mkdir -p /app/output");
    std::ofstream out(path);
    for (const auto& ln : lines) {
        out << "{\"epoch\":" << ln.epoch << ",\"lane_id\":\"" << json_escape(ln.lane_id)
            << "\",\"membership_digest\":\"" << json_escape(ln.membership_digest)
            << "\",\"pending_after_decay\":" << ln.pending_after_decay << "}\n";
    }
}

std::vector<ArpLine> read_arp_journal(const std::string& path) {
    std::vector<ArpLine> out;
    std::ifstream in(path);
    if (!in) return out;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        ArpLine ln;
        auto ep = line.find("\"epoch\"");
        if (ep != std::string::npos) {
            auto c = line.find(':', ep);
            try {
                ln.epoch = static_cast<uint64_t>(std::stoull(line.substr(c + 1)));
            } catch (...) {
            }
        }
        auto lid = line.find("\"lane_id\"");
        if (lid != std::string::npos) {
            auto q1 = line.find('"', lid + 9);
            if (q1 != std::string::npos) {
                auto q2 = line.find('"', q1 + 1);
                if (q2 != std::string::npos) ln.lane_id = line.substr(q1 + 1, q2 - q1 - 1);
            }
        }
        auto md = line.find("\"membership_digest\"");
        if (md != std::string::npos) {
            auto q1 = line.find('"', md + 20);
            if (q1 != std::string::npos) {
                auto q2 = line.find('"', q1 + 1);
                if (q2 != std::string::npos) {
                    ln.membership_digest = line.substr(q1 + 1, q2 - q1 - 1);
                }
            }
        }
        auto pd = line.find("\"pending_after_decay\"");
        if (pd != std::string::npos) {
            auto c = line.find(':', pd);
            try {
                ln.pending_after_decay = static_cast<uint32_t>(std::stoul(line.substr(c + 1)));
            } catch (...) {
            }
        }
        out.push_back(ln);
    }
    return out;
}

std::string flow_bytes_digest() {
    std::ifstream in("/app/output/run_traces/session.journal");
    if (!in) return md5_hex16("");
    std::string body((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    return md5_hex16(body);
}

struct Lineage {
    uint64_t pack_epoch = 0;
    uint64_t settle_epoch = 0;
    long seed = -1;
    std::string chain_prev;
    std::string chain_bind;
    std::string last_matrix;
};

uint64_t lineage_u64(const std::string& body, const std::string& key, uint64_t fallback) {
    auto pos = body.find("\"" + key + "\"");
    if (pos == std::string::npos) return fallback;
    auto colon = body.find(':', pos);
    if (colon == std::string::npos) return fallback;
    try {
        return static_cast<uint64_t>(std::stoull(body.substr(colon + 1)));
    } catch (...) {
        return fallback;
    }
}

long lineage_long(const std::string& body, const std::string& key, long fallback) {
    auto pos = body.find("\"" + key + "\"");
    if (pos == std::string::npos) return fallback;
    auto colon = body.find(':', pos);
    if (colon == std::string::npos) return fallback;
    try {
        return std::stol(body.substr(colon + 1));
    } catch (...) {
        return fallback;
    }
}

std::string lineage_str(const std::string& body, const std::string& key) {
    auto pos = body.find("\"" + key + "\"");
    if (pos == std::string::npos) return "";
    auto colon = body.find(':', pos);
    if (colon == std::string::npos) return "";
    auto q1 = body.find('"', colon);
    if (q1 == std::string::npos) return "";
    auto q2 = body.find('"', q1 + 1);
    if (q2 == std::string::npos) return "";
    return body.substr(q1 + 1, q2 - q1 - 1);
}

bool read_lineage(const std::string& path, Lineage& lin) {
    std::ifstream in(path);
    if (!in) return false;
    std::string body((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    lin.pack_epoch = lineage_u64(body, "pack_epoch", 0);
    lin.settle_epoch = lineage_u64(body, "settle_epoch", 0);
    lin.seed = lineage_long(body, "seed", -1);
    lin.chain_prev = lineage_str(body, "chain_prev");
    lin.chain_bind = lineage_str(body, "chain_bind");
    lin.last_matrix = lineage_str(body, "last_matrix");
    return true;
}

void write_lineage(const std::string& path, const Lineage& lin) {
    std::ostringstream body;
    body << "{\n  \"pack_epoch\": " << lin.pack_epoch << ",\n  \"settle_epoch\": "
         << lin.settle_epoch << ",\n  \"seed\": " << lin.seed << ",\n  \"chain_prev\": \""
         << json_escape(lin.chain_prev) << "\",\n  \"chain_bind\": \""
         << json_escape(lin.chain_bind) << "\",\n  \"last_matrix\": \""
         << json_escape(lin.last_matrix) << "\"\n}\n";
    std::ofstream out(path);
    out << body.str();
}

}  // namespace

int span_band(const std::vector<Row>& rows) {
    int m = 0;
    for (const auto& r : rows) {
        int v = r.lag_code < 0 ? -r.lag_code : r.lag_code;
        if (v > m) m = v;
    }
    return m;
}

std::string matrix_digest(const std::vector<Row>& rows) {
    std::vector<Row> ordered = rows;
    std::sort(ordered.begin(), ordered.end(),
              [](const Row& a, const Row& b) { return a.lane_id < b.lane_id; });
    std::string joined;
    for (size_t i = 0; i < ordered.size(); ++i) {
        const auto& r = ordered[i];
        if (i) joined += "|";
        joined += r.lane_id + "|" + r.facet_hex + "|" + std::to_string(r.loc_rc) + "|" +
                  std::to_string(r.img_rc) + "|" + std::to_string(r.bind_rc);
    }
    return md5_hex16(joined);
}

bool coherent(const std::vector<Row>& rows) {
    if (rows.empty()) return false;
    std::map<std::string, const Row*> by;
    for (const auto& r : rows) {
        if (r.lag_code != 0 || r.loc_rc != 1 || r.img_rc != 1 || r.bind_rc != 1) return false;
        by[r.lane_id] = &r;
    }
    static const std::pair<std::string, std::string> pairs[] = {
        {"axle", "axle_echo"}, {"rotor", "rotor_echo"}, {"stator", "stator_echo"}};
    for (const auto& p : pairs) {
        auto a = by.find(p.first);
        auto b = by.find(p.second);
        if (a == by.end() || b == by.end()) return false;
        if (a->second->facet_hex != b->second->facet_hex) return false;
    }
    return true;
}

int run_pipeline(const PipelineInput& in) {
    const std::string& root = in.env_root;

    auto ids = load_member_ids(root);
    auto weights = load_weights(root, in.seed);
    std::string triple = load_triple(root, in.seed);
    std::string staging = root + "/meta/staging.json";

    auto peer = expand_lanes(staging, ids);
    uint8_t peer_rc = peer.first;
    const auto& lanes = peer.second;
    std::string notes = JoinNotes(lanes);
    std::string digest = membership_digest_for(lanes);
    append_phase(in.profile == Profile::Prep ? "prep" : "seal", notes);

    std::string t = "T1|" + notes;
    std::string m = "M0|" + triple;
    std::vector<uint8_t> targets(t.begin(), t.end());
    std::vector<uint8_t> miimon(m.begin(), m.end());
    uint8_t ord_rc = order_gate(miimon, targets);

    std::system("mkdir -p /app/output/run_traces");
    std::string jrnl = "/app/output/run_traces/session.journal";
    std::string state_path = "/app/output/runtime_state.json";
    std::string arp_path = "/app/output/arp_journal.jsonl";
    std::string lineage_path = root + "/meta/lineage.json";
    std::string fp = compile_fingerprint(notes, triple, in.seed);
    std::string reloc = reloc_note_after_flush(1);

    RuntimeState prior;
    bool have_prior = read_runtime_state(state_path, prior);
    std::map<std::string, uint32_t> pending_map;
    for (const auto& lp : prior.lanes) pending_map[lp.lane_id] = lp.pending_arp_pressure;

    Lineage lin;
    read_lineage(lineage_path, lin);
    bool lineage_sound = true;
    if (!lin.chain_bind.empty()) {
        std::string expect = md5_hex16(chain_fold(lin.chain_prev) + "|" + lin.last_matrix + "|" +
                                       std::to_string(lin.settle_epoch));
        if (lin.last_matrix.empty() || lin.chain_bind != expect) lineage_sound = false;
    }

    bool compile_done = false;
    bool acked = false;
    RuntimeState next;
    next.epoch = prior.epoch;

    if (in.profile == Profile::Prep) {
        next.epoch = bump_epoch(have_prior ? prior.epoch : 0);
        lin.pack_epoch = bump_epoch(lin.pack_epoch);
        lin.seed = in.seed;
        write_lineage(lineage_path, lin);
        std::vector<ArpLine> arp_lines;
        for (const auto& lane : lanes) {
            uint32_t fixture = seed_pressure_for(lane);
            uint32_t pending = pending_map.count(lane) ? pending_map[lane] : fixture;
            uint32_t after = decay_arp_once(pending);
            LanePressure lp;
            lp.lane_id = lane;
            lp.pending_arp_pressure = after;
            lp.membership_digest = digest;
            next.lanes.push_back(lp);
            ArpLine al;
            al.epoch = next.epoch;
            al.lane_id = lane;
            al.membership_digest = digest;
            al.pending_after_decay = after;
            arp_lines.push_back(al);
        }
        write_runtime_state(state_path, next);
        write_arp_journal(arp_path, arp_lines);
        journal_commit(jrnl, fp, next.epoch, digest);
        compile_done = true;
    } else {
        auto arp_lines = read_arp_journal(arp_path);
        std::map<std::string, ArpLine> by_lane;
        for (const auto& al : arp_lines) by_lane[al.lane_id] = al;
        next.epoch = prior.epoch;
        for (const auto& lane : lanes) {
            uint32_t fixture = seed_pressure_for(lane);
            uint32_t persisted = pending_map.count(lane) ? pending_map[lane] : fixture;
            uint32_t merged = persisted;
            if (by_lane.count(lane)) {
                const auto& al = by_lane[lane];
                merged = merge_arp_pending(al.epoch, prior.epoch, al.membership_digest, digest,
                                           al.pending_after_decay, fixture, persisted);
            } else {
                merged = merge_arp_pending(0, prior.epoch, "", digest, 0, fixture, persisted);
            }
            LanePressure lp;
            lp.lane_id = lane;
            lp.pending_arp_pressure = merged;
            lp.membership_digest = digest;
            next.lanes.push_back(lp);
        }
        write_runtime_state(state_path, next);
        if (journal_ready(jrnl, fp)) compile_done = true;
        if (in.hook_replay) journal_ack(jrnl, fp);
        acked = journal_acked(jrnl);
    }

    std::vector<Row> rows;
    for (const auto& lane : lanes) {
        double w = weights.count(lane) ? weights[lane] : 0.0;
        std::string facet = facet_hex_for(canonical_id(lane), triple, reloc, w);
        int loc = (peer_rc == 1 && ord_rc == 1) ? 1 : 0;
        int img = (in.profile == Profile::Seal && compile_done && acked && loc == 1 &&
                   next.epoch >= 1 && lin.pack_epoch >= 1 && lin.seed == in.seed &&
                   lineage_sound)
                      ? 1
                      : 0;
        int lag = loc - img;
        rows.push_back(emit_row_phase(root, lane, loc, img, lag, facet));
    }

    std::string label = coherent(rows) ? "settled" : "drift";
    Summary sum;
    sum.rows_total = static_cast<int>(rows.size());
    sum.sync_label = label;
    sum.span_band = span_band(rows);
    sum.matrix_digest = matrix_digest(rows);
    sum.pack_epoch = lin.pack_epoch;
    sum.settle_epoch = lin.settle_epoch;
    sum.chain_bind = lin.chain_bind;
    write_report(in.out_path, rows, sum);

    if (in.profile == Profile::Seal) {
        std::ifstream rin(in.out_path);
        std::string report_body((std::istreambuf_iterator<char>(rin)), std::istreambuf_iterator<char>());
        std::string flow = flow_bytes_digest();
        if (sum.sync_label == "settled" && !gate_report_ok(report_body, flow)) {
            sum.sync_label = "drift";
        }
        if (sum.sync_label == "settled") {
            uint64_t settle_epoch = chain_arm(lin.pack_epoch);
            if (lin.settle_epoch != settle_epoch || lin.last_matrix != sum.matrix_digest) {
                std::string prev_bind = lin.chain_bind;
                lin.chain_prev = prev_bind;
                lin.last_matrix = sum.matrix_digest;
                lin.chain_bind = md5_hex16(chain_fold(prev_bind) + "|" + sum.matrix_digest + "|" +
                                           std::to_string(settle_epoch));
            }
            lin.settle_epoch = settle_epoch;
            write_lineage(lineage_path, lin);
        }
        sum.pack_epoch = lin.pack_epoch;
        sum.settle_epoch = lin.settle_epoch;
        sum.chain_bind = lin.chain_bind;
        write_report(in.out_path, rows, sum);
        sync_q2m_mirrors(root);
    }
    return 0;
}
