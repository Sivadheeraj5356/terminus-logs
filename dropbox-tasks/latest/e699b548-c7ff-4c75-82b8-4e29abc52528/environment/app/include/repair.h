#pragma once
#include "types.h"
#include <vector>

RepairResult repair_plan(CompactionPlan& plan, const std::vector<Fragment>& fragments, const Policy& policy);
