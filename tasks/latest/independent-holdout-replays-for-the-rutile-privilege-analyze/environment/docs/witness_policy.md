# Witness policy

Report attestation hashes the canonical edge-line witness.

Each edge contributes one line formatted `from:to:channel:weight` using the edge fields as emitted in the final sorted inventory. Lines are ordered by lexicographic comparison of the full line text. The attestation is the SHA-256 hex digest of those lines joined with newline separators and no trailing newline.
