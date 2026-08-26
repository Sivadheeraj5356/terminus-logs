# The cryogenic LNG tank boil-off mass-balance assay under /app must compute heat-

Submission: `dd6bfdff-def0-49e3-bcc9-6fdf76f700d5`  
Slug: `the-cryogenic-lng-tank-boil-off-mass-balance-assay-under-app`  
Latest archive: `dd6bfdff-def0-49e3-bcc9-6fdf76f700d5_submission_2026-07-14T05_40_29.887Z.zip`  
Revisions in Dropbox: 4

## Task summary

The cryogenic LNG tank boil-off mass-balance assay under /app must compute heat-leak evaporation from wetted-area heat influx, relief vent mass, and tank inventory mass conservation using the analytical contracts in /app/docs/input-schema.md, /app/docs/profiles.md, /app/docs/numeric-rounding.md, /app/docs/heat-leak-bog.md, /app/docs/inventory-balance.md, /app/docs/maintenance-exclusions.md, /app/docs/hash-contract.md, /app/docs/state-format.md, /app/docs/stage-export.md, /app/docs/action-catalog.md, /app/docs/output-schema.md, and /app/docs/directory-overrides.md. Run lng-boiloff-reconciler so it reads tank geometry, insulation profiles, cryogenic readings, transfers, and gauged inventories under /app/data, writes the durable heat-mass stage to /app/state/boiloff-stage.json, and writes /app/output/boiloff-report.json plus /app/output/corrective-actions.tsv. Absolute path overrides BOILOFF_INPUT_DIR, BOILOFF_OUTPUT_DIR, and BOILOFF_STATE_DIR must work. Results must be deterministic: unchanged physics inputs keep the same stage hash, and any change to tank metadata, readings, transfers, inventory snapshots, maintenance windows, or boil-off profiles must refresh the staged mass balance.

Required artifacts include: `/app/docs/input-schema.md`, `/app/docs/profiles.md`, `/app/docs/numeric-rounding.md`, `/app/docs/heat-leak-bog.md`, `/app/docs/inventory-balance.md`, `/app/docs/maintenance-exclusions.md`, `/app/docs/hash-contract.md`, `/app/docs/state-format.md`.

Author anonymous tagged this **hard** scientific-computing task (go, lng, cryogenic, boiloff, heat-leak, mass-conservation, scientific-computing).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `dd6bfdff-def0-49e3-bcc9-6fdf76f700d5_submission_2026-07-14T05_40_29.887Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
