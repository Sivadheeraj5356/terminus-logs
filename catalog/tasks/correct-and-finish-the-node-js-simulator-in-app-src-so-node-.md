# Correct and finish the Node.js simulator in `/app/src` so `node /app/src/cli.js 

Submission: `acbaea34-2ad7-45fb-bdf3-02e7023f1209`  
Slug: `correct-and-finish-the-node-js-simulator-in-app-src-so-node-`  
Latest archive: `acbaea34-2ad7-45fb-bdf3-02e7023f1209_submission_2026-07-15T08_07_37.760Z.zip`  
Revisions in Dropbox: 6

## Task summary

Correct and finish the Node.js simulator in `/app/src` so `node /app/src/cli.js --config <absolute-json-path> --out <absolute-directory>` produces reproducible thermal-cycle reports for a layered composite panel. The full config schema, update rules, and output schemas are in `/app/docs/thermal-cycle-contract.md`. Treat that file as the source of truth. The command must accept `--config` and `--out` exactly once, both with absolute paths. On success it should replace the output directory with exactly `field.csv`, `events.csv`, `summary.json`, `trace.csv`, `material_profile.csv`, and `stability.csv`. Bad arguments or bad config must fail before touching the requested output directory, while later runtime failures should leave any existing output intact.

Required artifacts include: `/app/src`, `/app/src/cli.js`, `/app/docs/thermal-cycle-contract.md`.

Author anonymous tagged this **hard** scientific-computing task (finite-difference, thermal-cycle, cure-kinetics, stress-relief, anisotropic-stencil).

Time estimates: expert ~150 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `acbaea34-2ad7-45fb-bdf3-02e7023f1209_submission_2026-07-15T08_07_37.760Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
