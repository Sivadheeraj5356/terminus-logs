# mx_pack schema and fixture formats

## Package JSON (`/app/output/mx_pack.json`)

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | int | `1` |
| `pack_id` | string | `mx_pack_v1` |
| `asset_counts` | object | ints: `nodes`, `edges`, `foreign_hits`, `cache_hits` |
| `runs` | array | each row: `id`, `n_probe`, `n_home`, `n_foreign`, `seal_hex` |
| `replay_digest` | string | 16 lowercase hex |
| `gate_digest` | string | 16 lowercase hex |
| `freshness` | array | each: `id`, `skew`, `gen_n`, `span`, `touch` |
| `classify` | array | each: `id`, `band` |
| `annex_note` | string | |

`seal_hex` is sixteen lowercase hex characters.

## Sign-tree line formats (`fixtures/sign/`)

| Path | Line shape |
|------|------------|
| `core.d/models.w` | `id cloud actor gen` |
| `sig.d/manifest.sx` | `name\|file\|parent` (`parent` is `-` for roots) |
| `sig.d/*.sx` | `id cloud actor gen` |
| `appr.d/bump.aw` | `id actor gen` |
| `ovl.d/e{N}.ov` | `id cloud actor` |
| `meta/epochs.cfg` | `floor=N`, `active=N,N,...` |
| `meta/revoke.jnl` | `id@epoch` |
| `meta/cut.cfg` | `cut_floor=N` |
| `meta/quorum.cfg` | `min_touches=N` |
| `certs.d/windows.crt` | `id not_before not_after` |
| `log.d/times.jnl` | `id integrated_time` |
| `witness/local.obs` | observational only (not package input schema) |

Blank lines and `#` comments are ignored in these tables.

## Held-out rows (`fixtures/xrows/*.yaml`)

YAML fields used by the kit: `span`, `min_g`, and a list of leaves each with `id` and `need`.

## Cache residue (`fixtures/cache_stale/`)

Optional `mix:<token>` lines. These files are residue fixtures, not sign-tree members.
