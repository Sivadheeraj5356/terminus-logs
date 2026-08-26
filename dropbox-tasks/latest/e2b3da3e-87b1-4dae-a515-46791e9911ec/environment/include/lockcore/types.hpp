#pragma once

#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace lockcore {

// Raised for any user-facing failure: invalid case/topology/forcing,
// CLI misuse, failed nonlinear solves, restore validation failures,
// and audit mismatches. main() catches this, prints a message to
// stderr, and exits non-zero without mutating existing outputs.
class LockctlError : public std::runtime_error {
public:
    explicit LockctlError(const std::string& what) : std::runtime_error(what) {}
};

struct CurveKnot {
    double level_m = 0.0;
    double volume_m3 = 0.0;
};

struct StorageCurve {
    std::vector<CurveKnot> knots;
};

struct SolverConfig {
    double initial_step_s = 30.0;
    double minimum_step_s = 0.46875;
    double maximum_step_s = 120.0;
    double volume_abs_tolerance_m3 = 1e-7;
    double volume_rel_tolerance = 1e-8;
    double newton_abs_tolerance_m3 = 1e-9;
    double newton_rel_tolerance = 1e-10;
    int maximum_newton_iterations = 12;
};

struct CaseSpec {
    int schema_version = 4;
    std::string case_id;
    int64_t start_time_s = 0;
    int64_t end_time_s = 0;
    int64_t output_interval_s = 0;
    std::string topology_path;
    std::string forcing_path;
    SolverConfig solver;
};

enum class NodeType { Storage, Boundary };
enum class LinkType { Gate, Weir, Pump };

struct NodeSpec {
    std::string node_id;
    NodeType node_type = NodeType::Storage;
    double initial_level_m = 0.0;
    int storage_curve_revision = 1;
    StorageCurve storage_curve;
};

struct LinkSpec {
    std::string link_id;
    LinkType link_type = LinkType::Gate;
    std::string from_node;
    std::string to_node;
    double discharge_coefficient = 0.0;
    double area_m2 = 0.0;
    double width_m = 0.0;
    double crest_level_m = 0.0;
    double initial_control = 0.0;
    double maximum_abs_flow_m3_s = 0.0;
};

struct Topology {
    int schema_version = 4;
    double gravity_m_s2 = 9.80665;
    std::vector<NodeSpec> nodes;
    std::vector<LinkSpec> links;
    std::map<std::string, double> initial_inflows;
};

enum class EventType {
    StorageCurveRevision = 0,
    BoundaryStage = 1,
    LinkControl = 2,
    ExternalInflow = 3,
    VolumeImpulse = 4
};

struct ForcingEvent {
    std::string event_id;
    int64_t source_seq = 0;
    int64_t time_s = 0;
    EventType event_type = EventType::ExternalInflow;
    std::string node_id;
    std::string link_id;
    double level_m = 0.0;
    double control = 0.0;
    double flow_m3_s = 0.0;
    double delta_volume_m3 = 0.0;
    int revision = 0;
    StorageCurve storage_curve;
};

struct SolverDiagnostics {
    int64_t accepted_substeps = 0;
    int64_t rejected_attempts = 0;
    int64_t newton_iterations = 0;
    double minimum_accepted_step_s = 0.0;
    double maximum_accepted_step_s = 0.0;
    double maximum_abs_mass_residual_m3 = 0.0;
};

struct ConservationState {
    double initial_total_storage_m3 = 0.0;
    double cumulative_external_volume_m3 = 0.0;
};

struct NodeSample {
    std::string node_id;
    std::string node_type;
    int curve_revision = 0;
    double level_m = 0.0;
    double volume_m3 = 0.0;
};

struct LinkSample {
    std::string link_id;
    std::string link_type;
    double flow_m3_s = 0.0;
    double control = 0.0;
};

struct ConservationSample {
    double current_total_storage_m3 = 0.0;
    double cumulative_external_volume_m3 = 0.0;
    double mass_residual_m3 = 0.0;
};

struct Sample {
    int64_t time_s = 0;
    std::vector<NodeSample> nodes;
    std::vector<LinkSample> links;
    ConservationSample conservation;
};

struct TransientReport {
    int schema_version = 4;
    std::string case_id;
    std::string case_digest_hex;
    bool completed = false;
    int64_t simulated_until_s = 0;
    std::vector<Sample> samples;
    SolverDiagnostics diagnostics;
    std::string audit_digest_hex;
};

}  // namespace lockcore
