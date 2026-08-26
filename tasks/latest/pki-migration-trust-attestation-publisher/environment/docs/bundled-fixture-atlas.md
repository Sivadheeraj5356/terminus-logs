# Bundled fixture atlas

bundle-migration-alpha under /app/fixtures/bundle-migration-alpha/ uses bundle_id bundle-migration-alpha-7c2.

Serial identifiers include SER-LEGACY (legacy backup.json with ASCII space in filename), SER-REVOKED, SER-WTREE, SER-DUP, SER-STALE, SER-NOPROOF, and SER-BADROOT.

The atlas exercises revoked, wrong_tree_size, duplicate_serial, stale_sth, missing_proof, untrusted_root, and trusted legacy backup rows across eight CT entries total.

Attest and publish must generalize to any migration bundle directory that satisfies migration-bundle-contract.md, not only bundle-migration-alpha.
