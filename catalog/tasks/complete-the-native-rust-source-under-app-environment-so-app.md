# Complete the native Rust source under `/app/environment` so `/app/bin/forest-aud

Submission: `0eca009c-c711-4f52-9d59-abc6b0e82c12`  
Slug: `complete-the-native-rust-source-under-app-environment-so-app`  
Latest archive: `0eca009c-c711-4f52-9d59-abc6b0e82c12_submission_2026-07-09T08_30_53.221Z.zip`  
Revisions in Dropbox: 1

## Task summary

Complete the native Rust source under `/app/environment` so `/app/bin/forest-audit` evaluates the bounded integer decision forest in `/app/data/demo.forest` against the stateful audit script in `/app/data/demo.audit` and writes `/app/output/certificates.json`. The command must also accept exactly three absolute positional paths in the order model, audit, and output; relative paths are invalid. The public contract in `/app/docs/forest-audit.md` defines the model and audit records, validation priority, nested `PUSH` and `POP` state behavior, exact counterfactual comparison, canonical report and hash, diagnostics, and safe publication rules. The completed command must handle other valid bounded forests and audit sessions, preserve an existing destination and any symbolic-link target on every failure, and rebuild with `cargo build --release --locked --offline`.

Required artifacts include: `/app/environment`, `/app/bin/forest-audit`, `/app/data/demo.forest`, `/app/data/demo.audit`, `/app/output/certificates.json`, `/app/docs/forest-audit.md`.

Author anonymous tagged this **hard** machine-learning task (model-robustness, counterfactual-search, decision-forests, stateful-audit, canonical-json).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `0eca009c-c711-4f52-9d59-abc6b0e82c12_submission_2026-07-09T08_30_53.221Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
