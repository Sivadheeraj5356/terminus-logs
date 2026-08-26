# We need the offline artifact release quorum gate finished before custody can sig

Submission: `36251034-f9a0-4a08-bdf2-9f9f16570311`  
Slug: `we-need-the-offline-artifact-release-quorum-gate-finished-be`  
Latest archive: `36251034-f9a0-4a08-bdf2-9f9f16570311_submission_2026-07-05T18_07_27.964Z.zip`  
Revisions: 1

## Task summary

We need the offline artifact release quorum gate finished before custody can sign off on binary promotions. The Zig tree under `/app` already compiles to `/app/bin/quorumgate`, but evaluation is still stubbed — nothing checks the Ed25519 counter-signatures or weighted quorum math from the contracts. Read `/app/docs/format.md`, `/app/docs/sign_contract.md`, and `/app/docs/digest_contract.md`. Bundled packs are under `/app/data/bundles/`.

Required artifacts include: `/app/bin/quorumgate`, `/app/docs/format.md`, `/app/docs/sign_contract.md`, `/app/docs/digest_contract.md`, `/app/data/bundles/`, `/app/output/release_audit.json`.

Author anonymous tagged this **hard** security task (zig, ed25519, quorum, release, custody).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `36251034-f9a0-4a08-bdf2-9f9f16570311_submission_2026-07-05T18_07_27.964Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
