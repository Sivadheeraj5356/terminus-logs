#include "replica.h"

bool check_replica_consistency(const std::vector<Fragment>& fragments, const Policy& policy) {
    for (const auto& f : fragments) {
        if ((f.replica_mask | policy.required_replica_mask) != policy.required_replica_mask) {
            return false;
        }
    }
    return true;
}
