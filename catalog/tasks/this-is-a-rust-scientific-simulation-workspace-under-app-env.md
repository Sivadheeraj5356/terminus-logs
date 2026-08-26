# This is a Rust scientific simulation workspace under `/app/environment`. The sui

Submission: `73111334-1c5d-482c-9281-a9e221708c19`  
Slug: `this-is-a-rust-scientific-simulation-workspace-under-app-env`  
Latest archive: `73111334-1c5d-482c-9281-a9e221708c19_submission_2026-07-19T13_31_05.718Z.zip`  
Revisions in Dropbox: 1

## Task summary

This is a Rust scientific simulation workspace under `/app/environment`. The suite models fog-of-war visibility replay over a rectangular cell grid, cadence-gated fade of stale coverage, ally observer pooling with resident-memory accounting, and a certified session ledger. The shipped build compiles and emits `/app/output/session_ledger.json`, but the ledger does not yet satisfy the full protocol contract. Plausible legacy code paths may still alias planes, use inclusive phase boundaries, or mis-scope checksums; the public contract is authoritative. Read the public contract in `/app/environment/docs/field_rules.md` and `/app/environment/docs/api.md` (dual-plane replay, half-open phase windows, cadence_trace vs cadence_trace_v3 checksum scope, trace retention, pool provenance, tick parsing/rejection, ledger_digest composition, and recovery epoch semantics are defined there). Mode caps and decay cadence live under `/app/environment/specs_r/`. Scenario fixtures are discovered at runtime from `/app/environment/cases/g2/`. Preview banner tokens appear in `/app/environment/docs/lex_k.tsv`.

Required artifacts include: `/app/environment`, `/app/output/session_ledger.json`, `/app/environment/docs/field_rules.md`, `/app/environment/docs/api.md`, `/app/environment/specs_r/`, `/app/environment/cases/g2/`, `/app/environment/docs/lex_k.tsv`, `/app/environment/docs/recover_k.txt`.

Author anonymous tagged this **hard** scientific-computing task (rust, simulation, state-replay, grid-geometry, provenance, memory-accounting, scientific-computing).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `73111334-1c5d-482c-9281-a9e221708c19_submission_2026-07-19T13_31_05.718Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
