# The image-rendering lab has ten diagnostic workstations that can no longer host 

Submission: `f197e256-a033-4e4f-ba72-a8f1d152b7a3`  
Slug: `the-image-rendering-lab-has-ten-diagnostic-workstations-that`  
Latest archive: `f197e256-a033-4e4f-ba72-a8f1d152b7a3_submission_2026-07-17T07_09_58.573Z.zip`  
Revisions: 1

## Task summary

The image-rendering lab has ten diagnostic workstations that can no longer host Valgrind or gdb sessions because a recent image refresh left them with an unsafe mix of ptrace, core-dump, group-membership, ulimit, and filesystem-permission settings. Your job is to author an Open Policy Agent Rego library under `/app/policy/` that translates each workstation's compliance state, sourced from the DuckDB inventory at `/app/inventory/workstations.duckdb` (view `v_workstation`), into an ordered remediation plan that matches the canonical decision matrix documented in `/app/postmortem/postmortem.md`. The postmortem is long but complete; every rule, every exact action string, and the required ordering are stated there. Your library must declare `package workstation.plan` and expose `actions` at `data.workstation.plan.actions`. For every workstation the emitted `{"workstation_id": <id>, "actions": [...]}` object must carry the id and the ordered action strings exactly as the postmortem prescribes, drawn from the seven documented action families (sysctl, systemd, group:add, ulimit, perms, fsattr, fixture-perms) with no duplicates, with all sysctl actions preceding any non-sysctl action, and with the workload-appropriate fixture-perms action as the terminal entry. All ten workstations must have their emitted plans exactly match their corresponding golden JSON files under `/app/golden/`.

Required artifacts include: `/app/policy/`, `/app/inventory/workstations.duckdb`, `/app/postmortem/postmortem.md`, `/app/golden/`.

Author anonymous tagged this **hard** system-administration task (opa, rego, duckdb, valgrind, gdb, sysctl, systemd, compliance, workstation-hardening).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `f197e256-a033-4e4f-ba72-a8f1d152b7a3_submission_2026-07-17T07_09_58.573Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
