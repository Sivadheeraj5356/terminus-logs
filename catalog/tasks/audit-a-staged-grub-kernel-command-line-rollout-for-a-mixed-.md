# Audit a staged GRUB/kernel-command-line rollout for a mixed Linux fleet using th

Submission: `a2ff05d7-b4f9-45e9-8efe-c2149d5d8cba`  
Slug: `audit-a-staged-grub-kernel-command-line-rollout-for-a-mixed-`  
Latest archive: `a2ff05d7-b4f9-45e9-8efe-c2149d5d8cba_submission_2026-07-16T18_35_27.684Z.zip`  
Revisions in Dropbox: 2

## Task summary

Audit a staged GRUB/kernel-command-line rollout for a mixed Linux fleet using the task materials in `/app/task_file`. The rollout state is supplied by the harness as records for candidate GRUB files, host boot/runtime state, loaded modules, and policy. Produce the effective GRUB defaults plus per-host blockers, warnings, aggregate summaries, remediation actions, and deterministic rollout waves from those records only; never inspect the real machine's filesystem, use the network, or install anything at runtime. Follow `/app/task_file/docs/SPEC.md` exactly. Its selected paths, GRUB assignment parsing, parameter-key handling, Secure Boot/lockdown/IOMMU/LUKS/module checks, exact finding strings, ordering rules, summaries, remediation grouping, and wave construction are all required for general mixed-fleet inputs, not just for the examples. Keep the documented entry points and report shapes in `/app/task_file/docs/API_REFERENCE.md` unchanged so the offline verifier can call the auditor.

Required artifacts include: `/app/task_file`, `/app/task_file/docs/SPEC.md`, `/app/task_file/docs/API_REFERENCE.md`.

Author anonymous tagged this **hard** system-administration task (grub, kernel-cmdline, boot-policy, fleet-audit, rollout).

Time estimates: expert ~180.0 min, junior ~1500.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `a2ff05d7-b4f9-45e9-8efe-c2149d5d8cba_submission_2026-07-16T18_35_27.684Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
