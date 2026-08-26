#pragma once

#include "lockcore/types.hpp"

#include <map>
#include <string>
#include <vector>

namespace lockcore {

struct ActiveCurve {
    int revision = 0;
    StorageCurve curve;
};

// Mutable simulation state that stays constant across a numerical interval
// (i.e. between forcing events): boundary levels, controls, inflows and
// active curves. Storage volumes are the integrated unknowns and are also
// tracked here for convenience between steps.
struct SimState {
    std::map<std::string, double> volumes;
    std::map<std::string, double> boundary_levels;
    std::map<std::string, double> link_controls;
    std::map<std::string, double> external_inflows;
    std::map<std::string, ActiveCurve> active_curves;
};

struct TopologyIndex {
    const Topology* topology = nullptr;
    std::map<std::string, const NodeSpec*> nodes;
    std::map<std::string, const LinkSpec*> links;
    std::vector<std::string> storage_ids;   // lexicographically sorted
    std::vector<std::string> boundary_ids;  // lexicographically sorted
};

TopologyIndex buildTopologyIndex(const Topology& topo);

SimState initialSimState(const TopologyIndex& idx);

// Applies one forcing event to `state`, validating the event's semantic
// preconditions (target existence/type, revision continuity, curve range,
// control ranges). Returns the external volume contributed at this instant
// (nonzero only for volume_impulse events).
double applyForcingEvent(const TopologyIndex& idx, SimState& state, const ForcingEvent& ev);

struct DerivResult {
    std::vector<double> dvdt;  // aligned with idx.storage_ids
    std::map<std::string, double> link_flows;
};

// Evaluates dV/dt for every storage node given a trial volume vector `V`
// (aligned with idx.storage_ids). Returns false (and leaves `out` unusable)
// if any storage volume in `V` lies outside its currently active curve.
bool evaluateDerivatives(const TopologyIndex& idx, const SimState& state, const std::vector<double>& V,
                          DerivResult& out);

// Sum of configured external inflows plus signed boundary-exchange flows
// entering the storage network (internal storage-to-storage flows are
// excluded), evaluated from a converged flow map.
double externalVolumeRate(const TopologyIndex& idx, const SimState& state,
                           const std::map<std::string, double>& link_flows);

double totalStorage(const std::vector<double>& V);

std::vector<double> volumesToVector(const TopologyIndex& idx, const SimState& state);
void vectorToVolumes(const TopologyIndex& idx, const std::vector<double>& V, SimState& state);

}  // namespace lockcore
