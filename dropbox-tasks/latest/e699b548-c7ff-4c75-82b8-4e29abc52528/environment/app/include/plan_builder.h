#pragma once
#include "types.h"
#include <vector>

CompactionPlan build_compaction_plan(const std::vector<Fragment>& fragments, const Policy& policy);
