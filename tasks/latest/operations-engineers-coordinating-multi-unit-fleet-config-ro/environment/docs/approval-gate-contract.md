# Approval gate contract

Policy file `/app/fixtures/policies/approval_policy.json` defines:

- `class_gates`: map decision_class → required role list (in order)
- `score_thresholds`: list of `{ "min_score": N, "extra_roles": [...] }` applied when impact_score >= min_score (all matching thresholds stack in ascending min_score order)
- `conditional`: when decision has `"flags"` containing `"exception"`, append role `exception_board` at the end if not already present

`approval_steps` is a list of `{ "decision_id", "roles": [...] }` in execution_order sequence. Roles within a step stay in policy-defined order with de-duplication preserving first occurrence.
