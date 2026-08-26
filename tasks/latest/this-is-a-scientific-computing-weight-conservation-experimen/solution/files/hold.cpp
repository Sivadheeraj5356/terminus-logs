#include "cryoready/hold.hpp"

namespace cryoready {

double hold_hours(double level_liters, const ModelSpec& model) {
    if (model.boil_off_l_per_day <= 0.0) {
        return 0.0;
    }
    const double reserve = model.usable_capacity_l * model.hold_reserve_fraction;
    const double remaining = level_liters - reserve;
    if (remaining <= 0.0) {
        return 0.0;
    }
    return (remaining / model.boil_off_l_per_day) * 24.0;
}

}  // namespace cryoready
