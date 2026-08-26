#pragma once

#include "lockcore/types.hpp"

#include <utility>

namespace lockcore {

bool curveContainsLevel(const StorageCurve& curve, double level_m);
bool curveContainsVolume(const StorageCurve& curve, double volume_m3);

// Piecewise-linear forward interpolation: level -> volume.
// Throws LockctlError if level_m lies outside the curve's closed range.
double volumeFromLevel(const StorageCurve& curve, double level_m);

// Piecewise-linear inverse interpolation: volume -> level.
// Throws LockctlError if volume_m3 lies outside the curve's closed range.
double levelFromVolume(const StorageCurve& curve, double volume_m3);

std::pair<double, double> volumeRange(const StorageCurve& curve);
std::pair<double, double> levelRange(const StorageCurve& curve);

}  // namespace lockcore
