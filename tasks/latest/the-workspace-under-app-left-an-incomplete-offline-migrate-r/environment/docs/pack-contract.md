# Pack and store

`/app/generated/plan-graph.json` uses schema `migrate-plan-graph-v1` with fields
`train`, `epoch`, `importers`, `peers`, `fingerprint`, and `packages` (each
with `name`, `version`, `path`, `contentDigest`).

Fingerprint is lowercase hex SHA-256 of the UTF-8 preimage:

`binds=<parts>|peers=<names>|train=<id>@<epoch>`

- `binds`: one `<importer>:<alias>=<package>` per direct edge, sorted by
  importer then alias, joined with `;`
- `peers`: extension-only peer names, sorted, joined with `,`
- `train`: active train id and epoch joined with `@`

Offline store `/app/offline-store/index.json` uses schema `migrate-store-index-v1`.
Keys are `name@version#` plus the first 16 hex chars of `contentDigest`.
`contentDigest` is the lowercase hex sha256 digest over canonical JSON of the
pack payload plus a trailing newline. Canonical JSON sorts object keys
recursively and uses compact separators. Each store record includes `name`,
`version`, `path`, `tarball`, `sha256` (lowercase hex sha256 of the tarball
bytes), `bytes` (tarball length), and `contentDigest`.

Pack payload shape:

```json
{
  "name": "...",
  "version": "...",
  "path": "...",
  "peers": ["..."],
  "markers": {"sealed": true}
}
```

Seal must replace the store set exactly (no ghost keys from prior seals).
Tarball bodies under `/app/offline-store/tarballs/` are pretty-printed JSON
(2-space indent) matching the payload plus trailing newline.
