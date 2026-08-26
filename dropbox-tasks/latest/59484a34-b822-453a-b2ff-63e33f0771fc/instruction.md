# PKI migration trust attestation publisher

Certificate Transparency auditors must rebuild a Merkle row snapshot from a post-cutover migration tarball, score each CT inclusion row against revocation chronology and signed-tree-head epochs, then publish a seal-bound ledger whose combined digest binds the snapshot row order.

After a botched certificate authority cutover, compliance teams inherit tarball directories that interleave X.509 material, Certificate Transparency log excerpts, signed tree heads, Merkle audit paths, revocation chronologies, issuance journals, and SHA-256 manifest ledgers. Some rows were re-issued under the same serial, some proofs attest inclusion in a tree size that no longer matches the bundled STH, and several filenames contain ASCII spaces that naive shell iterators mishandle.

The repository already contains a Go binary ctpki at /app/bin/ctpki and a Bash bundle gate at /app/scripts/pki_migration_bundle_gate.sh. Extend that code so a single offline workflow can score every certificate row and publish an attestation-bound CT ledger without network access.

## Snapshot artifacts

When attestation completes, these absolute paths exist:

/app/state/pki-evidence/ct_merkle_snapshot.json
/app/state/pki-evidence/disposition_matrix.json
/app/state/pki-evidence/publish_epoch.json
/app/output/published_ct_ledger.json

Attest reads one bundle directory, materializes the Merkle snapshot file, and writes the disposition matrix in the same process. Publish consumes the disposition matrix and the Merkle snapshot from attest, then writes the published ledger described in /app/docs/trust-ledger-contract.md and /app/docs/publish-seal-lineage.md. Publish does not re-open raw certificate files.

## Gate script contract

pki_migration_bundle_gate.sh validates layout per /app/docs/migration-bundle-contract.md. Manifest digest rows require full 64-character lowercase SHA-256 equality. The gate accepts certificate paths whose basenames include spaces.

## Disposition matrix rules

Disposition logic cross-checks revocation effective times, Merkle inclusion against the declared tree size, duplicate serial lineage with chronology tie-breakers, STH wall-clock epochs relative to inclusion rows, missing proof handling, and anchor membership against /app/docs/trusted-anchors.md. Rows land in trusted, rejected, or needs_review buckets per /app/docs/trust-disposition-scoring.md.

Helpers under /app/internal/decoy are not part of the attest scoring path.

## Contract library

Contracts live under /app/docs: migration-bundle-contract.md, trusted-anchors.md, ct-inclusion-proof.md, merkle-audit-rules.md, revocation-chronology.md, serial-lineage.md, sth-consistency.md, trust-disposition-scoring.md, trust-ledger-contract.md, publish-seal-lineage.md, ctpki-cli.md, bundled-fixture-atlas.md.

Operators invoke attest and publish through /app/bin/ctpki as documented in /app/docs/ctpki-cli.md. The migration gate script remains at /app/scripts/pki_migration_bundle_gate.sh.
