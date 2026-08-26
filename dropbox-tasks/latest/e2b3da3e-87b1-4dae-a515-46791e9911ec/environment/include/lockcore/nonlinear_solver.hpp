#pragma once

#include "lockcore/network_model.hpp"
#include "lockcore/types.hpp"

#include <map>
#include <vector>

namespace lockcore {

struct NewtonResult {
    bool converged = false;
    std::vector<double> V1;
    std::map<std::string, double> mid_link_flows;
    int64_t iterations = 0;
};

// Solves one implicit-midpoint step of duration `dt` starting from `V0`
// (aligned with idx.storage_ids), using damped Newton iterations with a
// finite-difference Jacobian and Gaussian elimination with partial
// pivoting. `state` supplies the fixed controls/boundary levels/inflows/
// curves for this interval.
NewtonResult solveImplicitMidpointStep(const TopologyIndex& idx, const SimState& state,
                                        const std::vector<double>& V0, double dt, const SolverConfig& cfg);

}  // namespace lockcore
