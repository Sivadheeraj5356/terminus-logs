# pnpm override / store pin contract

Override pin files live under `/app/overrides/deps/*.json`.
Local store archives live under `/app/pnpm-store/` and **must be real gzipped packages** (not 1-byte stubs) whose bytes hash to the pin integrity.

Required pins (exact JSON keys `name`, `provide`, `version`, `resolved`, `integrity`):
- fmt.json provide=fmt version 10.2.1
  resolved = file:///app/pnpm-store/fmt-10.2.1.tgz
  integrity = sha256:16de8120e52729f6199371abe65cf9be293fd1461d73727bb187934db6e43313
  no https / registry.npmjs.org / floating tags
- zlib.json provide=zlib version 1.3.1
  resolved = file:///app/pnpm-store/zlib-1.3.1.tgz
  integrity = sha256:f5639a1dc21583311e433c27c086f6009700df2c60ef12a7362d830be5f63907
- spdlog.json provide=spdlog version 1.13.0
  resolved = file:///app/pnpm-store/spdlog-1.13.0.tgz
  integrity = sha256:a6796ab08339bdb8a7b9be12d9baec92f38cb58434ea3f1ad3f1df991dfc0f4d
  must not declare provide=fmt

`/app/.npmrc` must contain exactly (order free; blank lines OK):
```
offline=true
store-dir=/app/pnpm-store
```
Empty `/app/legacy-pnpm-notes.txt` to exactly: `# emptied for pnpm`

`/app/package.json` `pnpm.overrides` must map fmt/zlib/spdlog to the file:///app/pnpm-store/…tgz URLs above (no registry hosts).
`/app/pnpm-lock.yaml` packages for those three must use the same file:// resolved URLs and matching `sha256:` integrities.
`/app/pnpm-workspace.yaml` must list `packages: ['.']`.

Sync `/app/config/deps.csv` as follows (clear `patch_url` on repaired rows):
- Every lane row for `dep:fmt` / `dep:zlib` / `dep:spdlog` → the file:// pnpm-store URLs and sha256 digests above (spdlog provide=`spdlog`).
- `edge,dep:legacy` **must also be synced** to `file:///app/pnpm-store/legacy-0.1.0.tgz` with
  `sha256:8242c9efd58c3303245f10ccb28374af24fd96b7b1ff80f5326f14908d8f13dc`.
- `gate,dep:jsonA` → `file:///app/pnpm-store/jsonA-1.0.0.tgz` +
  `sha256:c9bd4cda52a7a1ab8d9ee9f93ac2b53b444cf0986aea839d0eb92a196185ede0`.
- `gate,dep:jsonB` → provide `jsonalt` (not `json`) +
  `file:///app/pnpm-store/jsonB-1.0.0.tgz` +
  `sha256:4d716f3c27f14900e3b356fb27f6925ad6292dfd5b3ce284ab5bae4068276214`.
- Lane `lab` keeps drifted `dep:poison` version `0.2.0` with source_hash `sha256:ffff…f`
  against pin wrap `poison` version `0.1.0` / sha256 `000…1` (do not "fix" it).

## pnpm-report.json

Emitted at `/app/dist/pnpm-report.json`:
- `format_version` (int 1)
- `deps`: array sorted by `name`, each object exact keys
  `{name, provide, version, source_url, source_hash, mirror_ok}`
- `name` is the **bare override pin stem** from `/app/overrides/deps/<name>.json`
  (e.g. `fmt`, `zlib`, `spdlog`) — **not** the deps.csv coordinate form `dep:fmt`
- `legacy_cleared` JSON **boolean**
- `offline_pnpm_mode` JSON **boolean** `true` iff `.npmrc` enables `offline=true` (never a string)
- `cargo_packages`: crate package names in `sorted(crates/*/Cargo.toml)` path order
  (aa-graph → pnpmfix-cli → pnpmfix-core → zz-index ⇒ `pnpmfix-graph`, `pnpmfix-cli`, `pnpmfix-core`, `pnpmfix-index`)

`mirror_ok` is true only when **all** hold:
1. `source_url` starts with `file:///app/pnpm-store/`
2. the path exists, size > 32 bytes, and is a readable gzip member
3. sha256(file bytes) equals `source_hash` after normalizing — comparison **strips** an optional leading `sha256:` on either side

**Serialization (exact):** every `source_hash` written to `deps.csv` and every `deps[].source_hash` in `pnpm-report.json` MUST be the form `sha256:` + lowercase 64-hex (not bare hex).

`/app/scripts/release.sh` must **validate** pins/offline/legacy/archives (fail closed; exit non-zero on mismatch) and must **not** rewrite those files. It **must fail closed** when any repaired/migrated deps.csv row still has a non-empty `patch_url`. Release.sh must not read `/tests`.

**Structural (exact):** the body of `/app/scripts/release.sh` itself must contain the literal substring `overrides` or `overrides/deps`. Validation that only lives in a helper script (e.g. `validate.py`) that release.sh calls does **not** satisfy this — graders read `release.sh` text directly.
