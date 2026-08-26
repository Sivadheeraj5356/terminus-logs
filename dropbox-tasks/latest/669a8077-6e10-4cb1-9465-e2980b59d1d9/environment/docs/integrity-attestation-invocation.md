# Lot-release integrity attestation issuance

Quality-unit and compliance reviewers issue GMP lot-release integrity security reviews through /app/bin/gmp-lot-integrity-attestor.

Supported issuance modes are census and attest-release.

census requires --metadata pointing at the lot evidence dossier directory. It prints one compact JSON object to stdout with batch_id, qc_count, equipment_count, environmental_count, and documentation_count.

attest-release requires --metadata, --stage, and --output. The --metadata value must be an absolute directory unless BATCH_METADATA_DIR is set to a non-empty absolute directory, in which case the environment variable wins. The --stage and --output values must be absolute file paths.

attest-release writes the integrity staging capsule first, advances /app/state/release-auth-ledger.json, then writes the trust attestation by reading the staging capsule from disk. With the bundled base dossier it writes /app/state/batch-release-snapshot.json and /app/output/batch-release-audit.json. A lot on hold still writes both artifacts and exits with process status 1. A release-ready lot exits with process status 0.

Missing arguments, malformed dossier rows, relative override paths, or unknown issuance modes return process status 2 with a message on standard error.
