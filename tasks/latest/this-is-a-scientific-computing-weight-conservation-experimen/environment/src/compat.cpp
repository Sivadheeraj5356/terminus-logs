#include "cryoready/compat.hpp"

namespace cryoready {

bool specimen_compatible(const std::string& specimen_class, const std::string& vessel_cryogen_class) {
    if (specimen_class == vessel_cryogen_class) {
        return true;
    }
    if (specimen_class == "LHe" && vessel_cryogen_class == "LN2") {
        return true;
    }
    return false;
}

}  // namespace cryoready
