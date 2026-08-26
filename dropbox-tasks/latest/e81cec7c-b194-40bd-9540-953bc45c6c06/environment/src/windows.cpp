#include "cryoready/windows.hpp"

namespace cryoready {

bool in_maintenance(const Maintenance& maint, const std::string& vessel_id, long long epoch_unix) {
    for (const auto& w : maint.windows) {
        if (w.vessel_id != vessel_id) {
            continue;
        }
        if (epoch_unix >= w.start_unix && epoch_unix <= w.end_unix) {
            return true;
        }
    }
    return false;
}

}  // namespace cryoready
