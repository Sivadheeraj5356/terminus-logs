// wg_run driver — handshake reconcile emission for local-then-replay workflow.
//
// Reduction formulas (summary fields):
//
//   range_band = maximum absolute shift_code magnitude across all rows.
//
//   flow_digest = first 16 lowercase hexadecimal characters returned by
//   wg_md5_hex16 over the sorted concatenation of row material strings,
//   where each row contributes: peer_id|bind_hex|mux_rc|mark_rc|ov_rc|seal_rc
//   (integer rc fields encoded as decimal digits, fields joined by '|').
//   wg_md5_hex16 is defined in include/wg_md5.cpp.

#include "wg_api.hpp"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

extern int fn_h9(const char* audit_path, const char* trace_root, char* label_out, size_t label_cap);

namespace {

struct Args {
    Profile profile = Profile::Stage;
    std::string out_path = "/app/output/psk_rotate_report.json";
    bool hook_replay = false;
    bool status_view = false;
    int32_t variant_seed = 0;
};

std::string env_root() {
    const char* root = std::getenv("WG_ENV_ROOT");
    return root ? root : ".";
}

std::vector<std::string> read_lines(const std::string& path) {
    std::vector<std::string> out;
    std::ifstream in(path);
    std::string line;
    while (std::getline(in, line)) {
        if (!line.empty() && line[0] != '#') out.push_back(line);
    }
    return out;
}

Args parse_argv(int argc, char** argv) {
    Args args;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--profile" && i + 1 < argc) {
            args.profile = (std::string(argv[++i]) == "apply") ? Profile::Apply : Profile::Stage;
        } else if (arg == "--out" && i + 1 < argc) {
            args.out_path = argv[++i];
        } else if (arg == "--hook" && i + 1 < argc && std::string(argv[i + 1]) == "replay") {
            args.hook_replay = true;
            ++i;
        } else if (arg == "--variant-seed" && i + 1 < argc) {
            args.variant_seed = std::stoi(argv[++i]);
        } else if (arg == "--status-view") {
            args.status_view = true;
        }
    }
    if (args.hook_replay) args.profile = Profile::Apply;
    return args;
}

int32_t range_band(const std::vector<PeerRow>& rows) {
    int32_t max_abs = 0;
    for (const auto& row : rows) max_abs = std::max(max_abs, std::abs(row.shift_code));
    return max_abs;
}

std::string conv_label(const std::vector<PeerRow>& rows) {
    const std::vector<std::pair<std::string, std::string>> pairs = {{"peer_a", "peer_a_m"},
                                                                     {"peer_b", "peer_b_m"}};
    bool coherent = !rows.empty();
    for (const auto& row : rows) {
        if (row.shift_code != 0 || row.mux_rc != 1 || row.mark_rc != 1 || row.ov_rc != 1 ||
            row.seal_rc != 1) {
            coherent = false;
        }
    }
    for (const auto& [left, right] : pairs) {
        const PeerRow* la = nullptr;
        const PeerRow* lb = nullptr;
        for (const auto& row : rows) {
            if (row.peer_id == left) la = &row;
            if (row.peer_id == right) lb = &row;
        }
        if (la && lb && la->bind_hex != lb->bind_hex) coherent = false;
    }
    return coherent ? "settled" : "drift";
}

std::string json_escape(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c == '\\' || c == '"') out += '\\';
        out += c;
    }
    return out;
}

void write_report(const std::string& path, const std::vector<PeerRow>& rows) {
    auto slash = path.find_last_of('/');
    if (slash != std::string::npos) {
        std::string cmd = "mkdir -p " + path.substr(0, slash);
        std::system(cmd.c_str());
    }
    std::ostringstream body;
    body << "{\n  \"rows\": [\n";
    for (size_t i = 0; i < rows.size(); ++i) {
        const auto& row = rows[i];
        body << "    {\"peer_id\": \"" << json_escape(row.peer_id) << "\", \"mux_rc\": "
             << static_cast<int>(row.mux_rc) << ", \"mark_rc\": " << static_cast<int>(row.mark_rc)
             << ", \"ov_rc\": " << static_cast<int>(row.ov_rc) << ", \"seal_rc\": "
             << static_cast<int>(row.seal_rc) << ", \"shift_code\": " << row.shift_code << ", \"bind_hex\": \""
             << json_escape(row.bind_hex) << "\"}";
        if (i + 1 < rows.size()) body << ",";
        body << "\n";
    }
    body << "  ],\n  \"summary\": {\n"
         << "    \"rows_total\": " << rows.size() << ",\n"
         << "    \"conv_label\": \"" << conv_label(rows) << "\",\n"
         << "    \"range_band\": " << range_band(rows) << ",\n"
         << "    \"flow_digest\": \"" << flow_digest_rows(rows) << "\"\n"
         << "  }\n}\n";
    std::ofstream out(path);
    out << body.str();
}

void append_trace(const std::vector<PhaseTrace>& traces) {
    std::system("mkdir -p /app/output/run_traces");
    std::ofstream out("/app/output/run_traces/phase.jsonl");
    for (const auto& trace : traces) {
        out << "{\"phase\": \"" << json_escape(trace.phase) << "\", \"detail\": \""
            << json_escape(trace.detail) << "\"}\n";
    }
}

int run_status_view(const std::string& root) {
    char label_buf[32] = {0};
    const std::string audit = "/app/output/psk_rotate_report.json";
    const std::string trace_root = "/app/output/run_traces";
    int rc = fn_h9(audit.c_str(), trace_root.c_str(), label_buf, sizeof(label_buf));
    std::cout << label_buf << " " << rc << "\n";
    return rc == 1 ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
    auto args = parse_argv(argc, argv);
    auto root = env_root();
    if (args.status_view) return run_status_view(root);

    auto perm_tbl = load_perm_tbl(root + "/data/perm_tbl.toml");
    auto tag_tbl = load_ov_tbl(root + "/data/overlap_tbl.toml");
    auto peer_ids = read_lines(root + "/docs/peer_ids.txt");
    std::ifstream witness_in(root + "/w8g/staged/w8_chain.bin");
    std::string witness_text((std::istreambuf_iterator<char>(witness_in)),
                             std::istreambuf_iterator<char>());

    PipelineInput input{args.profile, args.hook_replay, &perm_tbl, &tag_tbl, witness_text, &peer_ids,
                        args.variant_seed};

    if (args.profile == Profile::Stage) {
        std::system(("mkdir -p " + root + "/w8g/staged").c_str());
        std::ofstream probe(root + "/w8g/staged/local_mux.token", std::ios::trunc);
        probe << "ok\n";
        std::ofstream alt(root + "/w8g/staged/dual_alt.bin", std::ios::trunc);
        alt << "primary\n";
    }

    auto [rows, traces] = run_pipeline(input);
    write_report(args.out_path, rows);
    append_trace(traces);

    std::ofstream witness_out(root + "/w8g/staged/w8_chain.bin", std::ios::trunc);
    witness_out << input.witness_text;
    return 0;
}
