#include "scan_cost.h"
#include <map>

uint64_t compute_scan_cost_units(const CompactionPlan& plan, const std::vector<Fragment>& fragments, const Policy& policy) {
    std::map<uint16_t, Fragment> by_id;
    for (const auto& f : fragments) by_id[f.id] = f;
    uint64_t cost = 0;
    for (uint16_t id : plan.fragment_ids) {
        cost += static_cast<uint64_t>(by_id[id].byte_size);
    }
    return cost;
}
