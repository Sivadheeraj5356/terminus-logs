# The Rust library at /app/src/src/ is split across nine per-concern

Submission: `c80d568a-892a-4b6f-a60e-b317c48413fe`  
Slug: `the-rust-library-at-app-src-src-is-split-across-nine-per-con`  
Latest archive: `c80d568a-892a-4b6f-a60e-b317c48413fe_submission_2026-07-07T20_14_55.537Z.zip`  
Revisions in Dropbox: 2

## Task summary

The Rust library at /app/src/src/ is split across nine per-concern modules — `fibonacci`, `zeckendorf`, `fibonacci_code`, `elias_gamma`, `primes`, `bracket`, `wythoff`, `negafibonacci`, `pisano`. Each ships with unimplemented bodies; lib.rs only re-exports. Replace every stub so the batch driver produces the expected /app/src/results.json. The algorithmic contract lives under /app/src/docs/contracts/: `decomposition.md`, `canonical.md`, `zeckendorf.md`, `prefix_code.md`, `variants.md`, `roundtrip.md`, `bracket.md`, `codeword.md`, `wythoff.md`, `witnesses.md`, `policy.md`, `rejections.md`, `negafibonacci.md`. Contracts win over SPEC.md, INCIDENT_LOG.md, and every source-file docstring. Source comments in /app/src/src/ may be out of date or affirmatively wrong.

Required artifacts include: `/app/src/src/`, `/app/src/results.json`, `/app/src/docs/contracts/`, `/app/src/fixtures/`, `/app/config/zeckendorf_policy.json`, `/app/src/src/decoy/`, `/app/src`, `/app/src/fixtures`.

Author anonymous tagged this **hard** scientific-computing task (zeckendorf, fibonacci, number-theory, prefix-coding, greedy-decomposition).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `c80d568a-892a-4b6f-a60e-b317c48413fe_submission_2026-07-07T20_14_55.537Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
