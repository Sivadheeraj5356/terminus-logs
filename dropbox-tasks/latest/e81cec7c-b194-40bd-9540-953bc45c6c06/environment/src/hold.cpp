#include "cryoready/hold.hpp"

namespace cryoready {

double hold_hours(double level_liters, const ModelSpec& model) {
    if (model.boil_off_l_per_day <= 0.0) {
        return 0.0;
    }
    if (level_liters <= 0.0) {
        return 0.0;
    }
    return (level_liters / model.boil_off_l_per_day) * 24.0;
}

}  // namespace cryoready
