# # YourList SMS Service Operations Runbook

Submission: `50a239c8-a85a-47a6-9ab7-c5b04b1890b6`  
Slug: `yourlist-sms-service-operations-runbook`  
Latest archive: `50a239c8-a85a-47a6-9ab7-c5b04b1890b6_submission_2026-07-11T03_24_14.084Z.zip`  
Revisions: 1

## Task summary

Build an **offline system-administration runbook package** for the YourList SMS microservice. Inputs are frozen production snapshots under `/app/input/` (PM2 process logs, nginx edge access log, environment file, Express mount sources, and sample request bodies). Write all artifacts under `/app/output/`. Do not modify the host, call Telnyx, or send SMS. Treat this as **configuration and log inventory work**: inventory env keys, document route mounts, parse process-manager HTTP lines, and emit the ops markdown/JSON pack the on-call runbook expects. Values must come from the inputs (exact JSON equality is checked). Key requirements: `required_env_vars` — `TELNYX_API_KEY`, `TELNYX_PHONE_NUMBER`, sorted. Do not add `TELNYX_FROM_NUMBER`.; `present_env_vars` — every `TELNYX_*` key in `env_snapshot.txt`, sorted.; `missing_env_vars` — required names absent from the snapshot, sorted. Formula: `[name for name in required_env_vars if name not in env_snapshot]`.; `unused_telnyx_vars` — present keys not referenced as `process.env.TELNYX_*` in `sms.js` + `smsService.js` (merge references first-seen across both files), sorted..

Required artifacts include: `/app/input/`, `/app/output/`.

Author anonymous tagged this **hard** system-administration task (pm2, nginx, runbook, environment, sysadmin, express).

Time estimates: expert ~150 min, junior ~210 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `50a239c8-a85a-47a6-9ab7-c5b04b1890b6_submission_2026-07-11T03_24_14.084Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
