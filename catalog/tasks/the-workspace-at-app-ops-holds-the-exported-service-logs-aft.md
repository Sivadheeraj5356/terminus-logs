# The workspace at /app/ops holds the exported service logs after the service was 

Submission: `cbca50ee-8019-4428-9c4d-8a403a0d2494`  
Slug: `the-workspace-at-app-ops-holds-the-exported-service-logs-aft`  
Latest archive: `cbca50ee-8019-4428-9c4d-8a403a0d2494_submission_2026-07-20T15_02_43.496Z.zip`  
Revisions in Dropbox: 2

## Task summary

The workspace at /app/ops holds the exported service logs after the service was rotated, reloaded, rolled back in one partition window, and exported again. Reconcile the operational authorities so export --root /app/ops --out /app/output/current produces a signed compliance bundle whose report reflects the final partition set, cursor lineage, and omission ledger. Read /app/environment/docs/contract.md, cursor_trace.md, ledger.md, manifest.md, and commands.md. They cover the event trace, SQLite checkpoint columns, manifest fields, digest formulas, acceptable terminal states, legacy v1 compatibility, and the export/verify commands.

Required artifacts include: `/app/ops`, `/app/output/current`, `/app/environment/docs/contract.md`, `/app/ops/runtime/cursor_trace.jsonl`, `/app/ops/logs/*.journal`, `/app/ops/state/export_ledger.sqlite`, `/app/ops/state/export_state.json`, `/app/ops/manifests/bundle_manifest.json`.

Author anonymous tagged this **hard** system-administration task (go, log-rotation, sqlite-ledger, service-reload, audit-bundle).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `cbca50ee-8019-4428-9c4d-8a403a0d2494_submission_2026-07-20T15_02_43.496Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
