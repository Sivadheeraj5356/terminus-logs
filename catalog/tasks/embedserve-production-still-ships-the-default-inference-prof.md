# EmbedServe production still ships the default inference profile with a static Ca

Submission: `3f540f50-b76d-40a6-98d9-8d35b289e2ac`  
Slug: `embedserve-production-still-ships-the-default-inference-prof`  
Latest archive: `3f540f50-b76d-40a6-98d9-8d35b289e2ac_submission_2026-07-11T17_15_30.559Z.zip`  
Revisions in Dropbox: 6

## Task summary

EmbedServe production still ships the default inference profile with a static Cargo denylist and permissive model-loading defaults. The PHP hardening CLI under `/app/environment` has scaffolding for SQLite inventory lookups, operations-bundle policy extraction, and tokenizer-sidecar advisory scanning, but it does not yet drive a full harden run from live RustSec evidence. Extend the CLI so profile `embedserve-default` (declared in `/app/environment/config/profiles.json`) is hardened through the normal pipeline:

Required artifacts include: `/app/environment`, `/app/environment/config/profiles.json`, `/app/environment/scripts/run_harden_cli.php`, `/app/out/harden_report.json`, `/app/data/embedserve_inventory.db`, `/app/docs/embedserve-operations-bundle.md`, `/app/environment/sidecar/tokenizer/Cargo.lock`, `/app/environment/fixtures/rustsec-advisory-db`.

Author anonymous tagged this **hard** machine-learning task (embedserve, sqlite, cargo-audit, tokenizer, ml-gateway).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `3f540f50-b76d-40a6-98d9-8d35b289e2ac_submission_2026-07-11T17_15_30.559Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
