# Implement the base-R data processor in `/app/radar_tilt_qc_patch_stack.R` so `Rs

Submission: `ca7883ce-d4ff-494b-9cca-bf4dfbc564b1`  
Slug: `implement-the-base-r-data-processor-in-app-radar-tilt-qc-pat`  
Latest archive: `ca7883ce-d4ff-494b-9cca-bf4dfbc564b1_submission_2026-07-05T15_34_36.857Z.zip`  
Revisions: 1

## Task summary

Implement the base-R data processor in `/app/radar_tilt_qc_patch_stack.R` so `Rscript /app/radar_tilt_qc_patch_stack.R TRACE` reads one radar tilt QC late-correction record stream, applies the full reconciliation contract in `/app/SPEC.md`, and emits one final normalized audit as exact `key=value` rows. Print exactly these fields, in this order: `active_records`, `zone_load`, `snapshots`, `obs_count`, `correction_count`, `snap_count`, `vacuum_count`, `revoke_count`, `latest_rev_sum`, `trace_hash`. Keep the implementation self-contained in base R and do not use network services or external weather standards.

Required artifacts include: `/app/radar_tilt_qc_patch_stack.R`, `/app/SPEC.md`.

Author anonymous tagged this **hard** data-processing task (weather, radar, qc, patch, audit).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `ca7883ce-d4ff-494b-9cca-bf4dfbc564b1_submission_2026-07-05T15_34_36.857Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
