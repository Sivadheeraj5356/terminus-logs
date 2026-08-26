# The host under `/app/environment` should make extension changes transactional: s

Submission: `47c7cafc-75fe-40a8-9709-540760275e36`  
Slug: `the-host-under-app-environment-should-make-extension-changes`  
Latest archive: `47c7cafc-75fe-40a8-9709-540760275e36_submission_2026-06-30T11_23_09.471Z.zip`  
Revisions in Dropbox: 1

## Task summary

The host under `/app/environment` should make extension changes transactional: stage payloads on disk, bump versions, undo following a bad step, and keep the published entitlement map aligned with what is actually loaded. Operators report three pain clusters. After an interrupted bump, restart cannot tell which half-finished step to continue from even though a durable byte log exists. Undo puts payloads back but callers still see grants that should have vanished. Fresh puts sometimes publish entitlements before backing modules are wired.

Required artifacts include: `/app/environment`, `/app/bin/hx_ctl`, `/app/output/ops_row_report.json`, `/app/environment/docs/formal_contract.md`, `/app/environment/docs/hook_cmds.txt`, `/app/environment/data/ord_table.toml`.

Author anonymous tagged this **hard** build-and-dependency-management task (ruby, plugin-host, transaction-journal, rollback, capability-map, kill-resume).

Time estimates: expert ~90 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `47c7cafc-75fe-40a8-9709-540760275e36_submission_2026-06-30T11_23_09.471Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
