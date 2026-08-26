# # Build the `foldpath` continuation command

Submission: `757876fb-ab33-40a2-b881-877eea29883a`  
Slug: `build-the-foldpath-continuation-command`  
Latest archive: `757876fb-ab33-40a2-b881-877eea29883a_submission_2026-07-16T21_32_07.941Z.zip`  
Revisions in Dropbox: 2

## Task summary

Extend the C11 toolkit in `/opt/foldpath` with a native executable at `/usr/local/bin/foldpath`. Keep `/usr/local/bin/foldmodel-check` installed and working. `make clean all install` must build both as regular native executables from source; do not replace either command with a script or symlink. Implement the complete observable contract below. The same detailed contract is also available at `/opt/foldpath/docs/acceptance_contract.md` as a working reference. The starter deliberately supplies the public types and headers, build system, fixtures, checker front-end, and compileable module boundaries. Its configuration, fingerprint, linear-algebra, model, state, output, and atomic-file implementations are scaffolds only. Strict parsing and validation, equations and Jacobians, deterministic pivoting, initial-tangent construction, raw-byte fingerprints, persistence and integrity, finite NDJSON, and atomic commit behavior are all intentionally unfinished. Completing those modules—or replacing them with an equivalent design—is part of this task, together with implementing the continuation engine and command parser. The installed starter `foldmodel-check` is a front-end over the same unfinished library and becomes semantically usable only after those modules are completed. Do not assume that a function is implemented merely because its declaration and a starter definition exist.

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** scientific-computing task (c, numerical-continuation, nonlinear-systems, adaptive-stepping, checkpointing).

Time estimates: expert ~900.0 min, junior ~6000.0 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `757876fb-ab33-40a2-b881-877eea29883a_submission_2026-07-16T21_32_07.941Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
