#pragma once
#include "types.h"
#include <string>

CompactionPlan export_plan_from_staging(
    const StagingSnapshot& snap,
    const std::vector<Fragment>& fragments,
    const Policy& policy);
