# Lock format

## v2 (current)

Schema: `/app/schemas/modpolicy.lock.schema.json`

Fields: `schema_version`, `goos`, `goarch`, `policy_revision`, `modules[]`, `resolution_digest`.

Each module entry: `path`, `version`, `source`, `policy_decision`, `replaces`.

## v1 legacy mapping

Legacy v1 lockfiles use `policy_code` single-letter encodings:

| Code | v2 `policy_decision` | Typical `source` |
|------|----------------------|------------------|
| P | `policy` | `mirror` |
| W | `workspace` | `workspace` |
| R | `replace` | `replace` |

`modpolicylock migrate-lock` must map codes bijectively and preserve module versions and replace metadata.

Witness digests for fixtures live in `/app/fixtures/legacy/v1/witness.json`.
