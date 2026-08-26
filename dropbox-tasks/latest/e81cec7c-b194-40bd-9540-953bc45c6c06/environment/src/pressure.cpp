#include "cryoready/pressure.hpp"

namespace cryoready {

double pressure_psia(double pressure_psig) {
    return pressure_psig + kAtmPsia;
}

bool pressure_ok(double pressure_psig, const ModelSpec& model) {
    return pressure_psig <= model.mawp_psia;
}

}  // namespace cryoready
