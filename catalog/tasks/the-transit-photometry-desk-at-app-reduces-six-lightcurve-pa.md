# The transit photometry desk at `/app` reduces six lightcurve packs under `/app/c

Submission: `716c7e42-795e-438c-9b8e-300243fb9428`  
Slug: `the-transit-photometry-desk-at-app-reduces-six-lightcurve-pa`  
Latest archive: `716c7e42-795e-438c-9b8e-300243fb9428_submission_2026-07-15T12_43_17.837Z.zip`  
Revisions in Dropbox: 2

## Task summary

The transit photometry desk at `/app` reduces six lightcurve packs under `/app/curves` (trap01, warmj, nept, hotspot, graze, quiet). A pack run straight through agrees with the independent ledger `/app/scripts/ref-depth` at the campaign cursor. Resuming a pack from its mid-campaign checkpoint keeps the residual column small, but the depth product at that cursor no longer matches the straight-through path, and resuming the same checkpoint a second time can land on a different value than the first for several packs. Nothing crashes; the divergence is numerical. Make the straight-through, first-resume, and second-resume depth products land on the same value for every pack, and make two independent resumes of one checkpoint agree. Then run `/app/scripts/run_desk.sh` to rebuild and refresh `/app/output/depth_report.json` and `/app/output/matrix.transcript`. A small residual column alone is not evidence that the depth products match. The fresh-only reference under `/app/legacy` reproduces the straight-through totals but does not settle restart parity; `/app/scripts/ref-depth` must keep agreeing with the straight-through depth. Keep the material repairs inside the photometry reduction, snapshot restore, and neighbor-aperture paths under `/app` — leave the independent ledger, curve packs, and supporting modules alone. Field names and matrix wiring live in `/app/docs/operations.md`.

Required artifacts include: `/app/curves`, `/app/scripts/ref-depth`, `/app/scripts/run_desk.sh`, `/app/output/depth_report.json`, `/app/output/matrix.transcript`, `/app/legacy`, `/app/docs/operations.md`.

Author anonymous tagged this **hard** scientific-computing task (exoplanet, transit, photometry, checkpoint, parity).

Time estimates: expert ~60 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `716c7e42-795e-438c-9b8e-300243fb9428_submission_2026-07-15T12_43_17.837Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
