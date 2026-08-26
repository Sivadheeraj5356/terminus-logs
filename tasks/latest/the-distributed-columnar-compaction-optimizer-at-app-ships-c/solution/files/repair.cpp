#include "repair.h"
#include "plan_builder.h"
#include "validate.h"

RepairResult repair_plan(CompactionPlan& plan, const std::vector<Fragment>& fragments, const Policy& policy) {
    RepairResult rr;
    ValidationResult before = validate_plan(plan, fragments, policy);
    if (before.ok) {
        rr.ok = true;
        rr.swaps = 0;
        rr.fingerprint = plan.fingerprint;
        return rr;
    }
    CompactionPlan fixed = build_compaction_plan(fragments, policy);
    plan = fixed;
    rr.swaps = plan.fragment_ids.size() >= 2 ? 1 : 0;
    ValidationResult after = validate_plan(plan, fragments, policy);
    rr.fingerprint = plan.fingerprint;
    if (!after.ok) {
        rr.ok = false;
        rr.primary_error = after.primary_error;
        return rr;
    }
    rr.ok = true;
    rr.primary_error.clear();
    return rr;
}
