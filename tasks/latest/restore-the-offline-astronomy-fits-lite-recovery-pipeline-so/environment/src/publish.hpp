#pragma once

#include "types.hpp"

#include <string>
#include <vector>

void publish_all(const std::string& work_dir,
                 const RuntimeConfig& cfg,
                 const RecoveryPlan& plan,
                 const Mosaic& mosaic,
                 const std::vector<SamplePoint>& samples,
                 const std::vector<double>& thresholds);
