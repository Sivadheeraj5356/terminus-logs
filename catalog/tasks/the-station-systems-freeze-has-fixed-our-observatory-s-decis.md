# The Station Systems Freeze has fixed our observatory's decision record, and the 

Submission: `53cba4ce-e6b5-4364-a7ef-77064ef0c814`  
Slug: `the-station-systems-freeze-has-fixed-our-observatory-s-decis`  
Latest archive: `53cba4ce-e6b5-4364-a7ef-77064ef0c814_submission_2026-07-16T19_16_03.622Z.zip`  
Revisions in Dropbox: 1

## Task summary

The Station Systems Freeze has fixed our observatory's decision record, and the spectral analysis host is due for its audit. The Java estimator under /app/service produces the station's FFT band-power spectra for the geomagnetic channels; its working tree, however, no longer reflects the record: the build manifest resolves against artifact versions whose approvals are not in force, request values reach the telemetry store as concatenated statement text contrary to station policy, and the estimator computes to a spectral methods revision that no longer governs. Restore the host to the decision record as of the freeze:

Required artifacts include: `/app/service`, `/app/service/target/spectra-svc.jar`, `/app/requests/samples.http`, `/app/audit/provenance_dossier.json`, `/app/archive/dossier_schema.md`, `/app/archive`.

Author Aaron Charley tagged this **hard** scientific-computing task (spectral-analysis, welch-method, geomagnetics, maven, dependency-audit).

Time estimates: expert ~150 min, junior ~300 min.

Harbor timeouts: agent 1500.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `53cba4ce-e6b5-4364-a7ef-77064ef0c814_submission_2026-07-16T19_16_03.622Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
