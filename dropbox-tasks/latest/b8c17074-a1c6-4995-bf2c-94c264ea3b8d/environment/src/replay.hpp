#pragma once

#include "types.hpp"

#include <string>
#include <vector>

RecoveryPlan build_recovery_plan(const std::string& data_dir, const std::string& work_dir, const std::vector<OrderEntry>& authority);
