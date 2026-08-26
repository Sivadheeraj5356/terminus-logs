# A NOAA-aligned mid-ocean ridge survey must reconstruct disputed ROV dive lanes a

Submission: `f4d8b626-6922-4b17-b1c3-2e21510bff99`  
Slug: `a-noaa-aligned-mid-ocean-ridge-survey-must-reconstruct-dispu`  
Latest archive: `f4d8b626-6922-4b17-b1c3-2e21510bff99_submission_2026-07-11T15_30_36.686Z.zip`  
Revisions in Dropbox: 3

## Task summary

A NOAA-aligned mid-ocean ridge survey must reconstruct disputed ROV dive lanes after calibration drift across the Clarion-Clipperton fracture zone. Sonar observers filed competing depth reports across north trench and south ridge lanes, hydrothermal vent anchors, and superseded calibration sweeps. The expedition control cell needs a reproducible chain that normalizes Ocean Expedition Log bundle provenance, arbitrates lane precedence under published dive policy, links survivor observations into a feature timeline, binds replay counters to staging witnesses, and exports a sealed expedition atlas for peer review. The expeditctl tool under /app integrates ingest-dive-log, resolve-precedence, reconcile-observations, and export-atlas. Invalid bundles exit non-zero with stderr tokens from /app/docs/ERROR_CODES.md. Persisted mirrors land under /app/state/{expedition_id}-dives.json, {expedition_id}-resolved.json, and {expedition_id}-reconciled.json per /app/docs/RECONCILE_ARTIFACTS.md. Atlas emission follows /app/docs/ATLAS_EXPORT.md, /app/docs/EXPEDITION_SEAL.md, and /app/docs/WITNESS_HASH.md with replay sequencing from /app/docs/REPLAY_COUNTER.md. When TB3_DIVE_DIR points at an absolute directory, bare dive bundle filenames resolve under that directory per /app/docs/HIDDEN_CORPUS.md. Durable behavior must survive the release rebuild described in /app/docs/VERIFIER_REBUILD.md.

Required artifacts include: `/app/docs/ERROR_CODES.md`, `/app/state/{expedition_id}-dives.json`, `/app/docs/RECONCILE_ARTIFACTS.md`, `/app/docs/ATLAS_EXPORT.md`, `/app/docs/EXPEDITION_SEAL.md`, `/app/docs/WITNESS_HASH.md`, `/app/docs/REPLAY_COUNTER.md`, `/app/docs/HIDDEN_CORPUS.md`.

Author anonymous tagged this **hard** data-processing task (ocean, expedition, precedence, reconcile, atlas, oel).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `f4d8b626-6922-4b17-b1c3-2e21510bff99_submission_2026-07-11T15_30_36.686Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
