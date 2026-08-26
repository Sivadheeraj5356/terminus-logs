# Pin norm (catalog w8_r3)

## Obligation 4 (coverage floor ordering)

On the closed fixture algebra for catalog w8_r3, k9ctl score must emit a scorecard whose under_tally reports zero non-staging rotation breaches. A breach is any non-staging rotation whose post-floor coverage ratio sits below ratio_min from `/app/environment/fixtures/k9/w8_catalog.json`, or any lane whose total sample count sits below floor_min before ratio aggregation.

Coverage ratio for a rotation is `sum(hits) / sum(total)` computed only over rows where `total >= floor_min`. Rows with `total < floor_min` are excluded before ratio aggregation, not averaged in afterward. under_tally counts non-staging rotations where the post-floor ratio is strictly less than ratio_min.

Closed algebra members are the staging slice (staging flag true) used only by the early precheck, and the non-staging rotations from the catalog during full k9ctl score replay.

## Obligation 9 (prior ruling invalidation)

When prior ruling tomb entries exist in `/app/environment/fixtures/k9/a8_tomb.jsonl`, any score block whose block_id matches a tomb entry must be removed before rescoring. Trace export must record one reopen event per removed block with detail `invalidate|<block_id>`.

## Obligation 12 (anchor precedence merge)

Contested label pairs from `/app/environment/fixtures/k9/pair_w3.json` merge by audit-anchor precedence: lower rank integer wins. When ranks tie, the label with higher weight wins. Lexical token order must not decide the winner.

## Scorecard members

Required members are schema_version (string 1.0), catalog_label, cover_digest, merge_digest, block_digest, parity_fp, under_tally, blocks, and coverage.

Digest helpers use standard sha256 hashing (hashlib-compatible sha256_hex). cover_digest hashes newline-joined `lane:ratio` pairs sorted by lane for the final non-staging rotation replay. merge_digest hashes newline-joined winner tokens from pair merges in fixture order. block_digest hashes newline-joined `block_id:block_hash` pairs sorted by block_id. parity_fp hashes ordered hold-store digest rows from view v_hold_ordered.

block_hash for each surviving block is sha256_hex of the UTF-8 string `block|<block_id>|<lane>|<ratio_label>` where ratio_label is the four-decimal coverage ratio string for that block lane.

## Precheck caveat

A green marker reading PRECHECK_OK in `/app/output/run_traces/precheck.txt` only means the staging slice path succeeded. Full k9ctl score must still close obligations 4, 9, and 12 under catalog w8_r3 replay.

## Pair-swap metamorphic note

Swapping the first two pair tokens before merge must change merge_digest while each block_digest stays coherent with its lane inputs.
