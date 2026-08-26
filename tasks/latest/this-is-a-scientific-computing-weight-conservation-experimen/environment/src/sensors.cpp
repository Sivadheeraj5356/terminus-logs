#include "cryoready/sensors.hpp"

namespace cryoready {

bool sensor_cal_ok(long long calibrated_until_unix, long long epoch_unix) {
    return calibrated_until_unix >= epoch_unix;
}

}  // namespace cryoready
