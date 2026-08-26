# Prize desk grading contract (authoritative)

Source of truth for `/app/output/report.json` from `/app/bin/gachaudit`.

## CLI

`/app/bin/gachaudit --input <sessions.json> --config /app/config/gacha.json --override /app/config/live_overrides.toml --ledger <ledger.json> --output <report.json>`

Audit knobs `hmac_key`, `pity_threshold`, `pity_gap_sec`, and `mac_domains` always come from `/app/config/gacha.json`. The override path may be passed but must not change those values. If the override file is missing, still keep base knobs — do not apply `/app/config/desk_fallback.json`. Leave `/app/data/sessions.json` and `/app/config/gacha.json` unmodified.

## Session prep

- Duplicate `session_id`: keep the highest `revision`; if revisions tie, keep the earliest `opened_at`.
- Process kept sessions in `opened_at` ascending order for pity.
- Colliding `pull_index` values keep the earliest array occurrence, then sort by `pull_index` ascending.

## Crypto

Per-domain MAC keys are `SHA256(utf8(hmac_key + "|" + label))` raw bytes, with labels from `mac_domains` in the base config (`draw`, `item`, `receipt`, `digest`).

- Draw roll: HMAC-SHA256 with the draw-domain key over `server_seed|session_id|pull_index` (zero-based); first eight digest bytes as big-endian uint64 divided by `2^64 - 1`.
- Item pick: item-domain key over `server_seed|session_id|pull_index|item` into the ascending-sorted tier pool.
- Receipt: receipt-domain key, lowercase hex, over `session_id|pull_index|item_id|rarity`.
- `server_seed_hash`: lowercase hex SHA256 of the UTF-8 `server_seed` string.
- `session_digest`: digest-domain key over `session_id` then kept receipts in pull order, `|`-joined.

## Pity ledger

- Ledger JSON: `{"entries": {"<player_id>|<banner_id>": <int>, ...}}` — keep the banner segment.
- Load before audit; save after.
- Pity is per player and banner. If the previous kept session for that pair has `opened_at` more than `pity_gap_sec` earlier, reset pity to 0 before this session (`pity_gap_sec` is `86400` from base config).
- Before each kept pull, if pity `>= pity_threshold - 1` and logged rarity is below `rare`, emit `pity_violation`. Expected draws floor to at least `rare` under that condition. Advance pity from logged outcomes (rare/epic → 0, else +1).
- If `seed_ok` is false for a session, do not update the ledger pity for that player|banner (`pity_at_end` stays `pity_at_start`).

## Anomalies and report

Kinds: `draw_mismatch`, `receipt_invalid`, `seed_hash_mismatch`, `pity_violation`, `receipt_reuse`.
`seed_hash_mismatch` uses `pull_index` `-1` and empty `item_id`. `receipt_reuse` when a receipt repeats later in the session. Anomalies stay in processing order; `anomaly_kinds` sorted unique.

Top-level: `summary`, `sessions`, `clean_session_ids`.
`summary`: `sessions_total`, `sessions_clean`, `sessions_tainted`, `pulls_total`, `anomaly_count`, `integrity_score = round(100 * sessions_clean / sessions_total, 2)`.
`sessions` sorted by `session_id` with fields `session_id`, `player_id`, `banner_id`, `status` (`clean`|`tainted`), `pulls_kept`, `pity_at_start`, `pity_at_end`, `seed_ok`, `session_digest`, `anomalies`, `anomaly_kinds`.
`clean_session_ids` lexicographic. Clean means `seed_ok` and empty anomalies.
