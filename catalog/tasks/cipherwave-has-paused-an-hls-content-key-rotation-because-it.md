# Cipherwave has paused an HLS content-key rotation because its signature, custody

Submission: `65e96c3c-58a3-4c78-8943-e6ee43dc326a`  
Slug: `cipherwave-has-paused-an-hls-content-key-rotation-because-it`  
Latest archive: `65e96c3c-58a3-4c78-8943-e6ee43dc326a_submission_2026-07-15T19_50_17.449Z.zip`  
Revisions in Dropbox: 2

## Task summary

Cipherwave has paused an HLS content-key rotation because its signature, custody, fragment-integrity, rollout-ledger, quorum, and authorization evidence does not initially agree. The required work product is the fixed incident's cryptographic security ruling, derived offline from the immutable `profile.toml`, `registry.json`, `trust.json`, `catalog.json`, `guardian-trust.json`, `rollout-ledger.json`, and complete `media/` tree under `/app/fixtures/visible`. The profile audit time is the sole time authority; wall-clock time, network data, environment variables, and bundled output are not trust sources. The complete normative contract is split across three documents that must be applied together: `/app/docs/security-contract.md` defines authentication, key custody, HLS evidence, lifecycle and decision precedence, rollout-ledger replay, checkpoint classification, the complete frontier, and resilient authorization; `/app/docs/artifact-contract.md` defines exact schemas, canonical bytes, ordering, nullability, digests, confirmations, certificate seal, and plan binding; `/app/docs/contract-map.md` defines authority roles, trust boundaries, registry semantics, deliverable boundaries, and the retained-path confidentiality rule. Local tools and intermediate methods are otherwise unconstrained.

Required artifacts include: `/app/fixtures/visible`, `/app/docs/security-contract.md`, `/app/docs/artifact-contract.md`, `/app/docs/contract-map.md`, `/app/out/cipherwave-incident`.

Author ijbello29 tagged this **hard** security task (hls, ed25519, aes-gcm, aes-cbc, key-rotation, authorization).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `65e96c3c-58a3-4c78-8943-e6ee43dc326a_submission_2026-07-15T19_50_17.449Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
