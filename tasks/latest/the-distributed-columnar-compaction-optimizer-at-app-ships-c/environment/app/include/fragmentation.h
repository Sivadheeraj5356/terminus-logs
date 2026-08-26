#pragma once
#include "types.h"
#include <vector>

uint32_t compute_fragmentation_index(const CompactionPlan& plan, const std::vector<Fragment>& fragments);
