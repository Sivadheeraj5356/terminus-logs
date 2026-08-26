# Recover the Blender render-node profile controller from the incomplete files und

Submission: `e56dc618-7e9e-4454-8ff2-34a782c9530a`  
Slug: `recover-the-blender-render-node-profile-controller-from-the-`  
Latest archive: `e56dc618-7e9e-4454-8ff2-34a782c9530a_submission_2026-07-19T17_42_36.880Z.zip`  
Revisions in Dropbox: 1

## Task summary

Recover the Blender render-node profile controller from the incomplete files under /app. Make install must provide /usr/local/bin/blendprofile, the blendprofile-reconcile@.service systemd template, and the blendprofile tmpfiles policy. The controller must safely create portable profiles, reconcile add-ons in dependency order, preserve generation history, and report configuration drift without repairing it. Support create --manifest PATH --root PATH --profile NAME --out PATH with optional --dry-run, and validate with the same required paths. Both commands write deterministic JSON reports. Create must publish a complete profile atomically or preserve the prior profile and report; validate must distinguish clean state, drift, and operational failure.

Required artifacts include: `/app/docs/blendprofile_contract.txt`, `/app/schemas/create_report.txt`, `/app/schemas/validate_report.txt`, `/app/schemas/state_records.txt`.

Author anonymous tagged this **hard** system-administration task (blender, render-farm, systemd, profile-rollout, drift-recovery, change-control).

Time estimates: expert ~300 min, junior ~660 min.

Harbor timeouts: agent 1200.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `e56dc618-7e9e-4454-8ff2-34a782c9530a_submission_2026-07-19T17_42_36.880Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
