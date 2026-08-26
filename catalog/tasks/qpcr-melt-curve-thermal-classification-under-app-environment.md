# qPCR melt-curve thermal classification under `/app/environment` must discharge f

Submission: `70025929-7ec4-4264-b5f7-af477cfbe171`  
Slug: `qpcr-melt-curve-thermal-classification-under-app-environment`  
Latest archive: `70025929-7ec4-4264-b5f7-af477cfbe171_submission_2026-07-20T08_58_21.235Z.zip`  
Revisions in Dropbox: 1

## Task summary

qPCR melt-curve thermal classification under `/app/environment` must discharge floating-point numeric policy for laboratory assays that arrive through an append-only observation journal. Measured melt temperatures relative to uplink setpoints must classify stress wells and band wells under the published tolerance policy. Active assay observations must stay stable when journal lines are reordered or transport-retried. Policy swaps must recompute thermal outcomes rather than reuse stale numeric products. Hand-written static JSON is not enough. Sources under `/app/environment` must be corrected so live products satisfy the laboratory contract. Build the environment with /app/environment/scripts/build_all.sh and then run the certification command from /app/environment with the journal, policy, output, and cache path arguments set to the assay inputs under /app/environment/data and /app/output. The four path options are public input overrides. The same command must work for other journals and policy files that obey /app/environment/docs/journal_protocol.md. That document is the laboratory contract for event kinds, logical ordering, thermal classification, package schema qPCR-attestation-v2, provenance fields journal_digest, config_digest, and cache_key, assay trace, digests, witnesses, cache identity, and atomic publication. Invalid runs must leave any prior output and cache bytes unchanged, and must not create a new output file when none existed. Work fully offline.

Required artifacts include: `/app/environment`, `/app/environment/scripts/build_all.sh`, `/app/environment/data`, `/app/output`, `/app/environment/docs/journal_protocol.md`.

Author anonymous tagged this **hard** scientific-computing task (qpcr, melt-curve, thermal-tolerance, floating-point, numeric-policy, scientific-computing).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `70025929-7ec4-4264-b5f7-af477cfbe171_submission_2026-07-20T08_58_21.235Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
