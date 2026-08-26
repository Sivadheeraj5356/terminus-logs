# The vibration-controls team has a multi-rate bench campaign from a closed-loop p

Submission: `4649aef0-d039-4d9f-b743-fae06d562380`  
Slug: `the-vibration-controls-team-has-a-multi-rate-bench-campaign`  
Latest archive: `4649aef0-d039-4d9f-b743-fae06d562380_submission_2026-07-19T05_43_16.271Z.zip`  
Revisions: 2

## Task summary

The vibration-controls team has a multi-rate bench campaign from a closed-loop pointing axis. Each capture contains the expected command response and the measured harmonic coordinates at several probes; the unexplained motion must be traced back through the calibrated sensitivity paths to the smallest exact set of source tones. The campaign at `/app/plant_lab/` is read-only and must remain byte-for-byte unchanged. On completion, `/app/src/harmonic_recovery.cpp` is C++17 source and `/app/build/harmonic-recovery` is its executable. With exactly two arguments—a campaign directory and a destination—the executable must recover any conforming campaign, replace the destination atomically on success, and return nonzero without replacing it when recovery is impossible or the records are invalid. Its default result belongs at `/app/source_spectrum.json`. The bench conventions and complete contract under `/app/docs/` are binding.

Required artifacts include: `/app/plant_lab/`, `/app/src/harmonic_recovery.cpp`, `/app/build/harmonic-recovery`, `/app/source_spectrum.json`, `/app/docs/`.

Author anonymous tagged this **hard** scientific-computing task (scientific-computing, control-systems, harmonic-reconstruction, frequency-response, exact-arithmetic).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `4649aef0-d039-4d9f-b743-fae06d562380_submission_2026-07-19T05_43_16.271Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
