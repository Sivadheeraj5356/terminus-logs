#include "lockcore/storage_curve.hpp"

namespace lockcore {

std::pair<double, double> volumeRange(const StorageCurve& curve) {
    if (curve.knots.size() < 2) throw LockctlError("storage curve needs at least two knots");
    return {curve.knots.front().volume_m3, curve.knots.back().volume_m3};
}
std::pair<double, double> levelRange(const StorageCurve& curve) {
    if (curve.knots.size() < 2) throw LockctlError("storage curve needs at least two knots");
    return {curve.knots.front().level_m, curve.knots.back().level_m};
}
bool curveContainsLevel(const StorageCurve& curve, double level_m) {
    auto [lo, hi] = levelRange(curve);
    return level_m >= lo && level_m <= hi;
}
bool curveContainsVolume(const StorageCurve& curve, double volume_m3) {
    auto [lo, hi] = volumeRange(curve);
    return volume_m3 >= lo && volume_m3 <= hi;
}
double volumeFromLevel(const StorageCurve& curve, double level_m) {
    if (!curveContainsLevel(curve, level_m)) throw LockctlError("level outside storage curve range");
    const auto& knots = curve.knots;
    for (size_t i = 0; i + 1 < knots.size(); ++i) {
        const auto& a = knots[i]; const auto& b = knots[i + 1];
        if (level_m >= a.level_m && level_m <= b.level_m) {
            if (level_m == a.level_m) return a.volume_m3;
            if (level_m == b.level_m) return b.volume_m3;
            return a.volume_m3 + (level_m - a.level_m) * (b.volume_m3 - a.volume_m3) / (b.level_m - a.level_m);
        }
    }
    return knots.back().volume_m3;
}
double levelFromVolume(const StorageCurve& curve, double volume_m3) {
    if (!curveContainsVolume(curve, volume_m3)) throw LockctlError("volume outside storage curve range");
    const auto& knots = curve.knots;
    for (size_t i = 0; i + 1 < knots.size(); ++i) {
        const auto& a = knots[i]; const auto& b = knots[i + 1];
        if (volume_m3 >= a.volume_m3 && volume_m3 <= b.volume_m3) {
            if (volume_m3 == a.volume_m3) return a.level_m;
            if (volume_m3 == b.volume_m3) return b.level_m;
            return a.level_m + (volume_m3 - a.volume_m3) * (b.level_m - a.level_m) / (b.volume_m3 - a.volume_m3);
        }
    }
    return knots.back().level_m;
}
}  // namespace lockcore
