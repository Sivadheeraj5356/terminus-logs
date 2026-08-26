# Move-rule store policy

The desk materializes `/app/run/move_rules.sqlite` from `/app/data/seed_bootstrap.sql`. Three table families must survive import: `legal_actions`, `combo_rules`, and `blocked_actions`.

The seeded `combo_rules` table stores comma-separated `p1_action,p2_action` prefixes. Baseline seed rows include `strike,blink` and `blink,strike`. Combo audit `matched_prefix` values must equal the prefix string from the matching store row.

## Orphan round ids

`legal_actions` may list `round_id` values that never appear in `/app/data/q7_a.csv` or `/app/data/q7_b.csv`. Overlay-only rounds present in `/app/data/q7_overlay.csv` still require legality rows in the store. The rules audit probe reports sorted orphan ids as `orphan_round_ids`.

## Store digest

The rules audit snapshot hashes a compact JSON object with lexicographically sorted keys:

1. `action_count` — row count in `legal_actions`.
2. `blocked_count` — row count in `blocked_actions`.
3. `combo_count` — row count in `combo_rules`.
4. `orphan_round_ids` — sorted ascending array.

SHA-256 the UTF-8 bytes of that JSON (no extra whitespace); lowercase hex digest becomes `store_digest`.

## desk_init expectation

`bash /app/scripts/desk_init.sh` must rebuild the SQLite file from seed SQL. An empty touch-only init leaves combo and blocked tables unreadable until the verdict lane re-imports, which breaks standalone rules probes.
