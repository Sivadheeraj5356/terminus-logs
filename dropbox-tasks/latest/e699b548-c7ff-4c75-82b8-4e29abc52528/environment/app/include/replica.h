#pragma once
#include "types.h"
#include <vector>

bool check_replica_consistency(const std::vector<Fragment>& fragments, const Policy& policy);
