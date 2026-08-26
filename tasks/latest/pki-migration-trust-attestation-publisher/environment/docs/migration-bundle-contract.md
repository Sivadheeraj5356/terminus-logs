# Migration bundle contract

Each bundle root contains bundle_meta.json, certificates/, ct_logs/, revocations.json, issuance.json, and manifests/.

The migration gate script validates layout and SHA-256 rows in manifests/bundle.sha256. Certificate filenames listed in manifests/files.txt may contain ASCII spaces and must be validated without shell word splitting.

Evaluate reads ct_logs/b161aa7f_entries.jsonl in file order. Each line supplies serial, leaf_index, timestamp, and leaf_hash for snap rows.
