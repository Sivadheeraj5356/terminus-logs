# Hash contract

source_hash is SHA-256 hex over these paths in fixed order, each preceded by the relative path string, a zero byte, file bytes, and a trailing zero byte:

tanks.csv, tank_readings.csv, transfer_events.csv, inventory_snapshots.csv, maintenance_events.csv, config/boiloff-profiles.json

stage_hash is SHA-256 hex of canonical JSON containing version, source_hash, and tanks array only.

stage_seal is SHA-256 hex of canonical JSON containing version, source_hash, stage_hash, and tanks array.

report_hash is SHA-256 hex of canonical JSON containing version, source_hash, stage_hash, total_tanks, balanced_tanks, imbalanced_tanks, tanks array, and corrective_actions array.

Canonical JSON for hashing (stage_hash, stage_seal, report_hash) is not the same as pretty-printed output files. Build the hash input string as follows:

1. Serialize the object with compact separators: comma between fields, colon between keys and values, no extra whitespace (Python json.dumps with separators (",", ":"); Go encoding/json.Marshal on a struct with matching field order and json tags).
2. On the resulting UTF-8 string, remove a trailing .0 from any JSON number that is an integer value: replace patterns like 10000.0 with 10000 when the .0 appears immediately before a comma, closing brace, or closing bracket. Integer-valued floats must not keep a .0 suffix in the canonical string.
3. SHA-256 the canonical UTF-8 bytes and encode as lowercase hex.

Go encoding/json typically emits integers without a .0 suffix; other JSON serializers may emit 10000.0 for float fields. After step 2, every implementation must produce the same canonical UTF-8 string so stage_hash, stage_seal, and report_hash are byte-identical for the same logical payload.

Field inclusion for each hash type is fixed: stage_hash hashes version, source_hash, and tanks only (no stage_hash or stage_seal keys inside that payload). stage_seal hashes version, source_hash, stage_hash, and tanks. report_hash hashes version, source_hash, stage_hash, total_tanks, balanced_tanks, imbalanced_tanks, tanks, and corrective_actions.
