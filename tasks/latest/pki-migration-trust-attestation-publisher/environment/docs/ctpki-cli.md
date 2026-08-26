# ctpki CLI

Subcommands: attest, publish.

attest flags: --bundle, --snapshot, --report

Writes /app/state/pki-evidence/ct_merkle_snapshot.json and /app/state/pki-evidence/disposition_matrix.json

publish flags: --report, --snapshot, --out

Requires --snapshot pointing at the Merkle snapshot produced by attest for the same bundle run. Writes /app/output/published_ct_ledger.json

Run /app/scripts/pki_migration_bundle_gate.sh before attest in production attestation flows.
