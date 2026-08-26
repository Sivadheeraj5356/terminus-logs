# Restore the offline astronomy FITS-LITE recovery pipeline so that the command:

Submission: `b8c17074-a1c6-4995-bf2c-94c264ea3b8d`  
Slug: `restore-the-offline-astronomy-fits-lite-recovery-pipeline-so`  
Latest archive: `b8c17074-a1c6-4995-bf2c-94c264ea3b8d_submission_2026-07-18T07_58_09.239Z.zip`  
Revisions: 1

## Task summary

Restore the offline astronomy FITS-LITE recovery pipeline so that the command: mosaicctl recover /app/data /app/work

Required artifacts include: `/app/data`, `/app/work`, `/app/environment`, `/app/docs`.

Author anonymous tagged this **hard** scientific-computing task (fits, checkpoint-recovery, wcs, scientific-reproducibility, c++).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `b8c17074-a1c6-4995-bf2c-94c264ea3b8d_submission_2026-07-18T07_58_09.239Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
