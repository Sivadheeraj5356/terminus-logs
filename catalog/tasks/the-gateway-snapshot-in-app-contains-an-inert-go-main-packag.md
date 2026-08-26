# The gateway snapshot in `/app` contains an inert Go `main` package where its

Submission: `00af3d22-15fc-4b54-ba81-3ec0858a85bb`  
Slug: `the-gateway-snapshot-in-app-contains-an-inert-go-main-packag`  
Latest archive: `00af3d22-15fc-4b54-ba81-3ec0858a85bb_submission_2026-07-17T18_42_52.458Z.zip`  
Revisions in Dropbox: 4

## Task summary

The gateway snapshot in `/app` contains an inert Go `main` package where its authorization engine should be. Complete that package so the resulting binary can decide a stream of service-mesh requests backed by primary macaroons and arbitrarily nested third-party discharges. This is a stateful proof-verification problem. The implementation must rebuild the chained HMACs, bind every discharge both to the primary proof and its exact parent edge, find the globally canonical assignment of single and threshold- quorum discharge tokens, evaluate normalized request caveats, and update persistent nonce and single-use proof state in request order. A discharge that is valid in isolation is not authorization unless it is attached at the correct place in the proof tree; unused, replayed, duplicate-identity, partially bound, and nested dead-end evidence must be handled exactly as specified. The verifier must combine exact chained-HMAC authentication with normalized caveat evaluation, immediate-parent attachment proofs, threshold quorum selection, and persistent replay state. Assignment is global: locally usable evidence may attach to the wrong edge, quorum members must have distinct authorities and proof identities, nested branches can invalidate lexically earlier choices, and both c

Required artifacts include: `/app/MACAROON_CONTRACT.md`, `/app/macaroon-audit`, `/app/input/inspection.json`, `/app/output/report.json`.

Author Anonymous tagged this **hard** security task (go, security, macaroons, hmac, authorization, constraint-resolution, quorum, replay-protection, backtracking).

Time estimates: expert ~480.0 min, junior ~1600.0 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `00af3d22-15fc-4b54-ba81-3ec0858a85bb_submission_2026-07-17T18_42_52.458Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
