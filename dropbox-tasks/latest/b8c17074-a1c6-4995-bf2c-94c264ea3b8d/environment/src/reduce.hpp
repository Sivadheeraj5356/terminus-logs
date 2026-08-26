#pragma once

#include "types.hpp"

#include <map>
#include <string>
#include <vector>

Mosaic reduce_tiles(const RuntimeConfig& cfg,
                    const std::map<std::string, Tile>& tiles,
                    const std::vector<OrderEntry>& authority,
                    const std::vector<CalibrationRow>& calibration,
                    const RecoveryPlan& plan);
