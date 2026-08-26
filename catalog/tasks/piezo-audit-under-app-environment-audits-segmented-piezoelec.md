# `piezo-audit` under `/app/environment` audits segmented piezoelectric resonator 

Submission: `452ce15a-1ed6-4248-86f6-04f3c6e89e06`  
Slug: `piezo-audit-under-app-environment-audits-segmented-piezoelec`  
Latest archive: `452ce15a-1ed6-4248-86f6-04f3c6e89e06_submission_2026-07-10T10_01_46.213Z.zip`  
Revisions: 1

## Task summary

`piezo-audit` under `/app/environment` audits segmented piezoelectric resonator calibration files across multiple chip families against dated, inheritable profile catalogs. Published batch reports, branched manifest history, profile-graph caching, and resonance digests disagree with `/app/environment/docs/contract.md` after repeated runs. Repair the Rust source under `/app/environment` so `cargo build --locked` produces a working `/app/environment/bin/piezo-audit`. The tool must parse chips with aliases, segments, and segment-level calibration overrides; resolve profiles with inheritance, effective-date revision selection, and deprecation windows; merge per-family `(chip_id, profile_id)` conflicts with last-file replacement; resolve alias collisions across the batch; maintain rollback-safe branched manifest history at `/app/output/resonance_manifest.json`; invalidate cached rows when either input bytes or the profile version fingerprint (`profile_graph_hash`) change; write output atomically on success; and compute schema v4 digests bound to profile lineage, provenance, and readings ordered by `(temp_c, line_index)`.

Required artifacts include: `/app/environment`, `/app/environment/docs/contract.md`, `/app/environment/bin/piezo-audit`, `/app/output/resonance_manifest.json`, `/app/output/resonance_report.json`, `/app/environment/fixtures/`, `/app/output/resonance_row_cache.json`.

Author anonymous tagged this **hard** scientific-computing task (rust, piezoelectric, resonator, temperature, frequency, audit).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `452ce15a-1ed6-4248-86f6-04f3c6e89e06_submission_2026-07-10T10_01_46.213Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
