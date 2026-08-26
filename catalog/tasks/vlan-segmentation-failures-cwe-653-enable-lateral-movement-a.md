# VLAN segmentation failures (CWE-653) enable lateral movement across network secu

Submission: `fd3ace50-acb1-4cef-8d85-4a5b73dc7d98`  
Slug: `vlan-segmentation-failures-cwe-653-enable-lateral-movement-a`  
Latest archive: `fd3ace50-acb1-4cef-8d85-4a5b73dc7d98_submission_2026-07-20T12_52_56.357Z.zip`  
Revisions: 3

## Task summary

VLAN segmentation failures (CWE-653) enable lateral movement across network security zones. The enforcement engine at `/app/bin/vlan-segmentation-enforce` processes 8 flows across 4 trunk ports from `/app/evidence/` and writes results to `/app/output/enforcement_result.json`. The output JSON contains `analysis_metadata`, `summary`, `violations`, `trunk_configuration_findings`, `native_vlan_analysis`, and `violation_breakdown`. The engine must detect four violation categories on cross-VLAN flows (same-VLAN flows produce no violations). A `double_tagging` violation fires only when the frame's outer_tag equals the trunk port's configured native VLAN (VLAN 1) — frames whose outer_tag matches their source VLAN are not double-tagging. This applies to both 0x8100 and 0x88A8 ethertypes. Double-tagging severity is `critical` when the flow targets critical service ports (1433/3306/5432, 22/3389), `high` otherwise. A `native_vlan_exploit` fires on the same flows where double_tagging is detected, always severity `critical`. A `zone_violation` fires when a flow's source-to-destination zone crossing appears in the zone policy's blocked_destinations; severity is `high` for management service ports (445/3389/22), `medium` otherwise. An `acl_bypass` fires when cross-VLAN traffic reaches destinations blocked by explicit subnet-targeted ACL deny rules, always severity `high`. ACL catch-all deny entries (e.g., seq 999 "deny any any") do not trigger acl_bypass findings. Double-tagged flows are not excluded from ACL bypass checks — they are evaluated against ACL rules like any other...

Required artifacts include: `/app/bin/vlan-segmentation-enforce`, `/app/evidence/`, `/app/output/enforcement_result.json`.

Author anonymous tagged this **hard** security task (vlan-security, network-segmentation, cwe-653, lateral-movement).

Time estimates: expert ~60.0 min, junior ~120.0 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `fd3ace50-acb1-4cef-8d85-4a5b73dc7d98_submission_2026-07-20T12_52_56.357Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
