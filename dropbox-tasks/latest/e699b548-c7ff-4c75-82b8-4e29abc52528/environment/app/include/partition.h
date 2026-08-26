#pragma once
#include "types.h"
#include <cstdint>
#include <vector>

bool same_partition_column(const Fragment& a, const Fragment& b, bool case_fold);
std::vector<Fragment> filter_partition(const std::vector<Fragment>& fragments, uint16_t partition_id);
