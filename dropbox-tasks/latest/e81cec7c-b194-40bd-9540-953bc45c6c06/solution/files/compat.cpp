#include "cryoready/compat.hpp"

namespace cryoready {

bool specimen_compatible(const std::string& specimen_class, const std::string& vessel_cryogen_class) {
    return specimen_class == vessel_cryogen_class;
}

}  // namespace cryoready
