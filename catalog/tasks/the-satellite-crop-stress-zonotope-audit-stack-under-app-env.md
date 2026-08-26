# The satellite crop-stress zonotope audit stack under /app/environment regenerate

Submission: `088d2445-fc50-4f80-9c6e-83cdcecf6b6d`  
Slug: `the-satellite-crop-stress-zonotope-audit-stack-under-app-env`  
Latest archive: `088d2445-fc50-4f80-9c6e-83cdcecf6b6d_submission_2026-07-20T06_09_14.911Z.zip`  
Revisions: 1

## Task summary

The satellite crop-stress zonotope audit stack under /app/environment regenerates /app/output/audit_report.json through the published runner. Default lanes can look coherent in stage echoes, then the terminal audit drifts under watermark-bound journal replay and rotation remaps: lane digests and floating-point nest spans disagree with the stage echo, cold regenerations drift across reruns if stage residue survives, a warm restart can diverge from the cold baseline, and history CHK blocks above the watermark (or compaction echoes beside the journal) appear to drive numerical digests when they should not. Do not hand-write the JSON; rebuild through the published runner. /app/environment/tools/hs_run.sh --all-lanes --rotations /app/environment/docs/rot_d.toml

Required artifacts include: `/app/environment`, `/app/output/audit_report.json`, `/app/environment/tools/hs_run.sh`, `/app/environment/docs/rot_d.toml`, `/app/environment/build.sh`, `/app/environment/docs/pact_a.md`, `/app/environment/docs/duty_c.md`, `/app/environment/data/wal44/`.

Author anonymous tagged this **hard** scientific-computing task (go, zonotope, numerical, floating-point, matrix, scientific-computing).

Time estimates: expert ~240 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `088d2445-fc50-4f80-9c6e-83cdcecf6b6d_submission_2026-07-20T06_09_14.911Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
