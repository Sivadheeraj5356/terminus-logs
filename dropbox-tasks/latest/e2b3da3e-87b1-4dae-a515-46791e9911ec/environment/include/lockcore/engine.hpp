#pragma once

#include "lockcore/types.hpp"
#include "lockcore/storage_curve.hpp"
#include "lockcore/flow_laws.hpp"
#include "lockcore/util.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace lockcore {

struct SimState {
    CaseSpec cas;
    Topology topo;
    std::vector<ForcingEvent> events;
    std::string forcing_bytes;
    std::string case_digest_hex;

    std::vector<std::string> storage_ids;
    std::vector<std::string> boundary_ids;
    std::map<std::string, double> volumes;
    std::map<std::string, double> boundary_levels;
    std::map<std::string, double> link_controls;
    std::map<std::string, double> external_inflows;
    std::map<std::string, StorageCurve> active_curves;
    std::map<std::string, int> curve_revisions;
    std::map<std::string, size_t> node_index;
    std::map<std::string, const NodeSpec*> node_by_id;
    std::map<std::string, const LinkSpec*> link_by_id;

    ConservationState conservation;
    SolverDiagnostics diagnostics;
    double next_step_s = 0.0;
    int64_t time_s = 0;
    std::vector<Sample> samples;
    size_t next_event_idx = 0;
    int64_t processed_bytes = 0;
    int64_t max_source_seq = 0;
};

std::string sha256_hex(const std::string& data);
std::string read_file(const std::string& path);
void write_atomic(const std::string& path, const std::string& content);
void ensure_parent_dirs(const std::string& path);

CaseSpec load_case(const std::string& path);
Topology load_topology(const std::string& path);
std::vector<ForcingEvent> load_forcing_from_bytes(const std::string& bytes);
std::string compute_case_digest(const CaseSpec& cas, const Topology& topo);

void init_sim(SimState& s, const CaseSpec& cas, const Topology& topo, const std::vector<ForcingEvent>& events,
              const std::string& forcing_bytes);
void apply_events_at(SimState& s, int64_t t);
Sample take_sample(SimState& s, int64_t t);
bool integrate_to(SimState& s, int64_t target_time);
TransientReport build_report(SimState& s, bool completed);
std::string serialize_report(const TransientReport& r);
std::string serialize_snapshot(const SimState& s);
void load_snapshot_into(SimState& s, const std::string& path);
std::string audit_digest_of_report_json(const std::string& report_without_digest_field);

int run_cli(int argc, char** argv);

}  // namespace lockcore
