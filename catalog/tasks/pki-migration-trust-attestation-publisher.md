# # PKI migration trust attestation publisher

Submission: `59484a34-b822-453a-b2ff-63e33f0771fc`  
Slug: `pki-migration-trust-attestation-publisher`  
Latest archive: `59484a34-b822-453a-b2ff-63e33f0771fc_submission_2026-07-12T16_39_14.283Z.zip`  
Revisions in Dropbox: 3

## Task summary

Certificate Transparency auditors must rebuild a Merkle row snapshot from a post-cutover migration tarball, score each CT inclusion row against revocation chronology and signed-tree-head epochs, then publish a seal-bound ledger whose combined digest binds the snapshot row order. After a botched certificate authority cutover, compliance teams inherit tarball directories that interleave X.509 material, Certificate Transparency log excerpts, signed tree heads, Merkle audit paths, revocation chronologies, issuance journals, and SHA-256 manifest ledgers. Some rows were re-issued under the same serial, some proofs attest inclusion in a tree size that no longer matches the bundled STH, and several filenames contain ASCII spaces that naive shell iterators mishandle.

Required artifacts include: `/app/bin/ctpki`, `/app/scripts/pki_migration_bundle_gate.sh`, `/app/state/pki-evidence/ct_merkle_snapshot.json`, `/app/state/pki-evidence/disposition_matrix.json`, `/app/state/pki-evidence/publish_epoch.json`, `/app/output/published_ct_ledger.json`, `/app/docs/trust-ledger-contract.md`, `/app/docs/publish-seal-lineage.md`.

Author anonymous tagged this **medium** security task (x509, ct-log, merkle-snapshot, publish-seal-lineage, ca-migration-tarball).

Time estimates: expert ~240 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `59484a34-b822-453a-b2ff-63e33f0771fc_submission_2026-07-12T16_39_14.283Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
