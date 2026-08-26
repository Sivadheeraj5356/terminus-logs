# Timeline resume contract

Emit writes `/app/output/timeline_resume_report.json` with:

- `runs`: scenario rows in `config/scenario_catalog.toml` order
- `resume_digest`: lowercase hex SHA-256 of canonical JSON for `runs` only
- `timeline_hash`: must equal `resume_digest`
- `epoch_notes`: non-empty strings, one per scenario in catalog order; each must contain `epoch`

## Run row schema

Trace bundles under `traces/` carry `labels`, `wal_segments`, `automation.pre_raw`, `automation.post_raw`, `list_file`, `locale`, `target.path`, `views`, `stepback_event`, and `clock_skew` (decoy field — see precedence notes).

| Field | Type | Meaning |
|-------|------|---------|
| `name` | string | Scenario id from the catalog |
| `label_pick` | string | Resolved visible timeline label |
| `label_epoch` | int | Epoch of the chosen label row |
| `pre_id` | int | Effective pre automation id |
| `post_id` | int | Effective post automation id |
| `wal_cursor` | int | Highest WAL segment sequence merged |
| `scope_visible` | int | 1 when mount-view quorum satisfied; else 0 |
| `row_tag` | string | Lowercase sha256 hex over UTF-8 `name:label_pick:pre_id:post_id:wal_cursor:scope_visible` |
| `provenance` | string[] | Authority sources that contributed |

## Digests

`resume_digest` hashes canonical JSON for `runs` only (`json.dumps(runs, separators=(",", ":"), sort_keys=True)`).

`row_tag` hashes `name:label_pick:pre_id:post_id:wal_cursor:scope_visible` via `openssl dgst -sha256 -hex`.

Replay precedence, checkpoint reuse, WAL merge, locale lists, retention recycle, mount quorum, and handoff journal rules are in `/app/environment/docs/precedence_notes.md`.
