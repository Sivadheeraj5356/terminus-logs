#pragma once

#include "lockcore/network_model.hpp"
#include "lockcore/types.hpp"

#include <vector>

namespace lockcore {

struct SolverRuntimeState {
    double next_step_s = 0.0;
    int64_t accepted_substeps = 0;
    int64_t rejected_attempts = 0;
    int64_t newton_iterations = 0;
    double minimum_accepted_step_s = 0.0;
    double maximum_accepted_step_s = 0.0;
    double maximum_abs_mass_residual_m3 = 0.0;
    bool has_accepted_any = false;
};

struct ConservationRuntimeState {
    double initial_total_storage_m3 = 0.0;
    double cumulative_external_volume_m3 = 0.0;
};

struct SimulationRequest {
    int64_t case_start_time_s = 0;
    int64_t case_end_time_s = 0;
    int64_t output_interval_s = 0;
    int64_t begin_time_s = 0;   // current simulated time to resume/start from
    int64_t stop_time_s = 0;    // target time to integrate through (inclusive)
    // Events with time_s strictly greater than begin_time_s, in canonical order.
    std::vector<ForcingEvent> pending_events;
};

struct SimulationOutcome {
    int64_t simulated_until_s = 0;
    std::vector<Sample> samples;
    SimState final_state;
    SolverRuntimeState solver;
    ConservationRuntimeState conservation;
};

// Integrates the network from `req.begin_time_s` through `req.stop_time_s`,
// applying forcing events at exact boundaries, sampling at the documented
// output grid, and maintaining conservation/solver diagnostics. Throws
// LockctlError on any unrecoverable numerical or event failure.
SimulationOutcome runSimulation(const TopologyIndex& idx, const SolverConfig& cfg, SimState state,
                                 SolverRuntimeState solver, ConservationRuntimeState conservation,
                                 const SimulationRequest& req);

}  // namespace lockcore
