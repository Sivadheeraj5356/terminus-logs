# Produce the offline GMP lot-release integrity attestation artifacts under /app f

Submission: `669a8077-6e10-4cb1-9465-e2980b59d1d9`  
Slug: `produce-the-offline-gmp-lot-release-integrity-attestation-ar`  
Latest archive: `669a8077-6e10-4cb1-9465-e2980b59d1d9_submission_2026-07-12T19_14_42.896Z.zip`  
Revisions in Dropbox: 3

## Task summary

Produce the offline GMP lot-release integrity attestation artifacts under /app for quality-unit and compliance reviewers. This is a regulated release-governance security review. The security analysis reads the authoritative lot evidence dossier at /app/environment/metadata/base, materializes the normalized integrity staging capsule at /app/state/batch-release-snapshot.json, advances the release-authorization continuity ledger at /app/state/release-auth-ledger.json, and writes the paired trust attestation at /app/output/batch-release-audit.json. Security control contracts live in /app/docs/metadata-contract.md, /app/docs/qc-policy.md, /app/docs/equipment-policy.md, /app/docs/environmental-policy.md, /app/docs/documentation-policy.md, /app/docs/staging-snapshot.md, /app/docs/authorization-ledger.md, /app/docs/report-schema.md, and /app/docs/integrity-attestation-invocation.md. Every lot must be classified against quality-control approval and late signoff rules, manufacturing equipment release and calibration grace, environmental excursion windows, and approved release documentation types. Control evaluation order, blocker identifiers, metadata_digest construction, generated_at handling, staging_seal, evaluation_seq, and hold versus released attestation status must match those security contracts exactly. Issuance modes and absolute-path arguments are defined only in /app/docs/integrity-attestation-invocation.md. Re-running attest-release on unchanged dossier evidence must keep snapshot and report gate math stable while evaluation_seq advances in the ledger and report....

Required artifacts include: `/app/environment/metadata/base`, `/app/state/batch-release-snapshot.json`, `/app/state/release-auth-ledger.json`, `/app/output/batch-release-audit.json`, `/app/docs/metadata-contract.md`, `/app/docs/qc-policy.md`, `/app/docs/equipment-policy.md`, `/app/docs/environmental-policy.md`.

Author anonymous tagged this **hard** security task (gmp-release-governance, integrity-attestation, calibration-trust-control, excursion-window-policy, authorization-continuity-ledger, pharma-compliance-security).

Time estimates: expert ~60 min, junior ~120 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `669a8077-6e10-4cb1-9465-e2980b59d1d9_submission_2026-07-12T19_14_42.896Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
