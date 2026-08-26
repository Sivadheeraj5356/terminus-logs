# Policy index schema

SQLite database at `/app/var/policy-index/policy.db`.

## Tables

### pins

| Column | Type | Notes |
|--------|------|-------|
| path | TEXT | Module path |
| version | TEXT | Pinned version |
| goos | TEXT | GOOS selector |
| goarch | TEXT | GOARCH selector |
| policy_revision | TEXT | Org policy revision id |
| decision | TEXT | Policy decision string |

Primary key: `(path, goos, goarch, policy_revision)`.

### decision_cache

| Column | Type | Notes |
|--------|------|-------|
| path | TEXT | Root module path |
| version | TEXT | Root module version |
| goos | TEXT | Target GOOS |
| goarch | TEXT | Target GOARCH |
| policy_revision | TEXT | Active revision |
| payload_json | TEXT | Serialized module graph |

Primary key: `(path, version, goos, goarch, policy_revision)`.

Cache identity must include all primary-key fields.

### index_meta

Single row (`id = 1`):

| Column | Type | Notes |
|--------|------|-------|
| policy_revision | TEXT | Current revision |
| index_complete | INTEGER | 1 when fully indexed |
| write_epoch | INTEGER | Monotonic write generation |

## Source of truth for pins

Static input: `/app/var/module-mirror/policy/pins.jsonl` ingested by `modpolicylock reindex`.

## Interrupted refresh drill

`/app/scripts/interrupt-reindex.sh` writes roughly half of the pin rows from `pins.jsonl` but sets `index_meta.index_complete=1` early. That partial shape is intentional for recovery drills. `modpolicylock reindex` and `modpolicylock reindex --resume` must finish every pin row before advertising completeness, and a clean reindex versus a resumed reindex after the drill must yield identical resolution digests for the same request and platform.
