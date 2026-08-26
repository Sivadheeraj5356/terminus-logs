# Estimate the physical parameters of the non-calibration chirped spectral sources

Submission: `7d73c410-0195-4b91-88ff-76496407c011`  
Slug: `estimate-the-physical-parameters-of-the-non-calibration-chir`  
Latest archive: `7d73c410-0195-4b91-88ff-76496407c011_submission_2026-07-16T19_36_00.395Z.zip`  
Revisions: 2

## Task summary

Estimate the physical parameters of the non-calibration chirped spectral sources present in `/app/observations/`. The array samples below Nyquist, so the same source can appear as different aliases across instruments, and true source frequencies are not limited to any single instrument's observed baseband. `/app/catalog.sqlite` supplies the instrument clocks and calibration tones needed for the inverse spectral fit; calibration tones are references for the fit and must not be reported as unknown sources. Write the merged source estimates to `/app/output/events.json` and `/app/output/recovered.sqlite`. The notes in `/app/spec/` define the sample-window format, instrument constants, and required fields; one physical source should appear once even when several instruments observe different aliases of it. `/app/bin/recover` should perform the estimation from the current `/app/catalog.sqlite` and `/app/observations/` at runtime and write matching JSON and SQLite outputs.

Required artifacts include: `/app/observations/`, `/app/catalog.sqlite`, `/app/output/events.json`, `/app/output/recovered.sqlite`, `/app/spec/`, `/app/bin/recover`.

Author anonymous tagged this **hard** scientific-computing task (spectral-inversion, aliasing, chirp-estimation, inverse-problem).

Time estimates: expert ~420 min, junior ~780 min.

Harbor timeouts: agent 1800s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `7d73c410-0195-4b91-88ff-76496407c011_submission_2026-07-16T19_36_00.395Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
