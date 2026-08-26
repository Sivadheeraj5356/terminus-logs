# The navmesh tile baker under `/app` turns gridded walk tapes into stitched tile 

Submission: `7e3911b7-a546-4134-937c-c6138037a4b5`  
Slug: `the-navmesh-tile-baker-under-app-turns-gridded-walk-tapes-in`  
Latest archive: `7e3911b7-a546-4134-937c-c6138037a4b5_submission_2026-07-16T20_53_57.258Z.zip`  
Revisions in Dropbox: 1

## Task summary

The navmesh tile baker under `/app` turns gridded walk tapes into stitched tile polygons with border portal links. Continuous matrix legs look healthy on quick inspection, but pause-resume legs on the same scenario drift: parity checks fail, border weld counts change, link digests diverge, and area overlays at tile seams disagree with their cold twin. Pad-weighted tapes can also corrupt continuous digests when pad / resume state leaks into the weld. Rebuild through `/app/ci/build_and_load.sh` and emit `/app/output/nav_audit.json` matching `/app/doc/nav_audit_contract.txt`. Copy `schema_anchor` from `/app/stubs/schema_anchor.txt`. Pause-resume parity fields are in `/app/stubs/replay_contract.txt`. Tape grammar is in `/app/doc/semantics.txt`.

Required artifacts include: `/app/ci/build_and_load.sh`, `/app/output/nav_audit.json`, `/app/doc/nav_audit_contract.txt`, `/app/stubs/schema_anchor.txt`, `/app/stubs/replay_contract.txt`, `/app/doc/semantics.txt`, `/app/cfg/runtime.toml`, `/app/data/`.

Author anonymous tagged this **medium** scientific-computing task (navmesh, tile-stitch, volume-grid, checkpoint, simulation).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `7e3911b7-a546-4134-937c-c6138037a4b5_submission_2026-07-16T20_53_57.258Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
