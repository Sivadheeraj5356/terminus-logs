#pragma once
#include "types.h"
#include <vector>

ValidationResult validate_plan(const CompactionPlan& plan, const std::vector<Fragment>& fragments, const Policy& policy);
