# The Raman thermometry package at `/app` computes temperature from Stokes/anti-St

Submission: `948b1f30-f154-4afc-af02-1a5d43fdeeff`  
Slug: `the-raman-thermometry-package-at-app-computes-temperature-fr`  
Latest archive: `948b1f30-f154-4afc-af02-1a5d43fdeeff_submission_2026-07-20T09_25_08.696Z.zip`  
Revisions: 3

## Task summary

The Raman thermometry package at `/app` computes temperature from Stokes/anti-Stokes intensity ratios for sample `raman_calib_2025_001`. The output report at `/app/output/report.json` currently gives physically wrong temperatures — the reported value is inconsistent with the detected peak positions and intensity ratio in the spectrum. Fix the code so the reported temperature is physically consistent with the measured spectrum. Specifically, the Stokes and anti-Stokes peaks should each be detected as the single highest-intensity point within ±15 cm⁻¹ of their expected positions. The reported Raman shift (`parameters.raman_shift_cm` and `summary.peak_shift`) is the signed value (Stokes wavenumber − anti-Stokes wavenumber)/2, which is negative since Stokes sits below the laser line. The temperature must be derived from the absolute value of that shift and the measured intensity ratio. The Bose-Einstein population factor must be the exact form, not a high-temperature approximation.

Required artifacts include: `/app/output/report.json`, `/app/data/raman_spectrum.json`.

Author anonymous tagged this **hard** scientific-computing task (raman-spectroscopy, stokes-anti-stokes, bose-einstein, thermometry, optical-spectroscopy).

Time estimates: expert ~60.0 min, junior ~120.0 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `948b1f30-f154-4afc-af02-1a5d43fdeeff_submission_2026-07-20T09_25_08.696Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
