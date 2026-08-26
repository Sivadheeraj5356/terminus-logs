# The telemetry spectral audit in `/app/environment` no longer produces reproducib

Submission: `d1077eb1-a6a7-4f98-ba15-b647f105b0ac`  
Slug: `the-telemetry-spectral-audit-in-app-environment-no-longer-pr`  
Latest archive: `d1077eb1-a6a7-4f98-ba15-b647f105b0ac_submission_2026-07-14T12_13_48.757Z.zip`  
Revisions: 5

## Task summary

The telemetry spectral audit in `/app/environment` no longer produces reproducible reports after revisioned schema-version 3 packs and resumable processing were introduced. Repair `/app/bin/hann_energy_audit` so it conforms to `/app/docs/contract.md`, `/app/docs/pack-v3.md`, `/app/docs/spectral-processing.md`, and `/app/docs/checkpoint-and-seals.md`, while preserving the documented schema-version 2 behavior. It must deterministically replay sample and calibration revisions, reconstruct and calibrate sparse timelines, apply the documented frame-quality, gap, detrending, Hann, Goertzel, weighted-band, and peak rules, and emit the canonical report and seals. The audit report at `/app/output/report.json` must carry top-level `schema_version`, ordered `scenarios`, and a `summary` object as specified in the contract docs. The CLI must work with arbitrary `--pack` and nested `--out` paths plus the optional schema-version 3 `--checkpoint` path. It must resume only valid matching partial work, produce byte-identical results for semantically equivalent packs, and leave existing reports and checkpoints unchanged on malformed input, stale state, or any other failure. Fix the C++ source, rebuild and install it through the existing CMake project, and generate `/app/output/report.json` through the normal CLI; static output files or script replacements are not acceptable.

Required artifacts include: `/app/environment`, `/app/bin/hann_energy_audit`, `/app/docs/contract.md`, `/app/docs/pack-v3.md`, `/app/docs/spectral-processing.md`, `/app/docs/checkpoint-and-seals.md`, `/app/output/report.json`.

Author anonymous tagged this **hard** scientific-computing task (signal-processing, goertzel, spectral-analysis, numerical-methods, cmake).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `d1077eb1-a6a7-4f98-ba15-b647f105b0ac_submission_2026-07-14T12_13_48.757Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
