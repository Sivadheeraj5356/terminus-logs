#include "cryoready/fill.hpp"

namespace cryoready {

double fill_fraction(double level_liters, const ModelSpec& model) {
    if (model.usable_capacity_l <= 0.0) {
        return 0.0;
    }
    return level_liters / model.usable_capacity_l;
}

bool fill_in_range(double fraction, const ModelSpec& model) {
    return fraction >= model.min_fill_fraction && fraction <= model.max_fill_fraction;
}

}  // namespace cryoready
