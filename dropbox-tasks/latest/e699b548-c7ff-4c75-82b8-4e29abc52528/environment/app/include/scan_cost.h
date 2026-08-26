#pragma once
#include "types.h"
#include <vector>

uint64_t compute_scan_cost_units(const CompactionPlan& plan, const std::vector<Fragment>& fragments, const Policy& policy);
