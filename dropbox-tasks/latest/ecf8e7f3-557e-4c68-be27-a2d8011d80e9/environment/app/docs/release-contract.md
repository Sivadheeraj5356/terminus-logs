# Release contract

`/app/scripts/release.sh` must:
1. Validate override JSON pins / `.npmrc` / legacy notes / `package.json` overrides / `pnpm-lock.yaml` / pnpm-store archive digests per pnpm-contract.md (fail closed; do not rewrite those files). **Must also fail closed** if any repaired deps.csv row (`dep:fmt` / `dep:zlib` / `dep:spdlog`, and migrated file:// rows such as `dep:legacy` / `dep:jsonA` / `dep:jsonB`) still has a non-empty `patch_url`. The body of `release.sh` itself must contain the literal substring `overrides` or `overrides/deps` (helpers alone do not satisfy graders).
2. Confirm the workspace is offline-ready: `.npmrc` has `offline=true` and `store-dir=/app/pnpm-store`, and override pins / lockfile / package.json all resolve to matching `file:///app/pnpm-store/…tgz` URLs (no registry remotes). Do **not** require a live `pnpm install`.
3. Clear `/app/dist`, emit `pnpm-report.json` (schema in pnpm-contract.md).
4. `cargo build --release --locked --offline -p pnpmfix-cli`.
5. Package **only** each `release_matrix.csv` lane (ignore decoy lane JSON not listed).
6. Never read `/tests` (verifier baselines are isolated). A “do not read /tests” comment is fine; do not `cp`/`cat`/`source` verifier paths. At grading time agent-controlled `release.sh` / `pnpmfix` run with `/tests` unavailable.

## Bundle layout

`dist/bundles/pnpmfix-<lane>/`:

```
bin/pnpmfix
VERSION                 # exactly "pnpmfix 0.8.6\n"
LICENSES.txt
share/lane-policy.json  # {lane, retention_hops}
share/edges.csv
share/artifacts.csv
share/deps.csv
share/xor.csv
share/mirrors.csv
share/pins.csv
share/bans.csv
share/forbidden-hosts.csv
share/run-smoke.sh      # must invoke inspect with --forbidden-hosts
share/inspect-preview.json
```

`inspect-preview.json` and `run-smoke.sh` live under **`share/` only** — not at the bundle root.

`share/run-smoke.sh` must be executable and assign the outfile with the **exact** unquoted form `OUT=${1:-…}` (uppercase `OUT`; do **not** wrap `${1:-…}` in quotes). Default when `$1` is omitted is `share/inspect-preview.json` under the bundle root. Then invoke `bin/pnpmfix inspect … --edges … --forbidden-hosts … --out "$OUT"`. Also pass `--lane`. Build with `cargo build --release --locked --offline -p pnpmfix-cli`.

**LICENSES.txt byte rule:** concatenate every file under `/app/licenses/` in **sorted basename order**. For each file, append the file’s **raw** contents and then one extra `\n`. Do **not** strip trailing newlines already present — that yields blank lines between entries. Must include substantive Apache-2.0 and MIT bodies.

Tarballs: `dist/pnpmfix-<lane>-linux-x86_64.tar.gz` at dist root (archive root `pnpmfix-<lane>/`).
Must be byte-stable under `SOURCE_DATE_EPOCH` (default `1700000000`): set tar `--mtime`, and compress with **`gzip -n`**.
Only `dist/bundles/` may be a directory at the dist root.

## release-manifest.json

Top-level keys **exactly**: `format_version`, `package`, `workspace`, `fetch`, `bundles`.

```json
{
  "format_version": 1,
  "package": {
    "name": "pnpmfix-cli",
    "version": "0.8.6",
    "target": "x86_64-unknown-linux-gnu"
  },
  "workspace": [
    {
      "name": "<crate>",
      "version": "0.8.6",
      "license": "<resolved>",
      "dependencies": ["<sorted>"]
    }
  ],
  "fetch": { "...identical to dist/pnpm-report.json..." },
  "bundles": [
    {
      "lane": "<lane>",
      "archive": "pnpmfix-<lane>-linux-x86_64.tar.gz",
      "archive_sha256": "<hex>",
      "binary_sha256": "<hex>",
      "policy_sha256": "<hex of share/lane-policy.json>",
      "inspect_preview_sha256": "<hex of share/inspect-preview.json>",
      "artifact_count": <int>,
      "hold_count": <int>,
      "risk_score_total": <int>
    }
  ]
}
```

`workspace` entries use Cargo **package** names (e.g. `pnpmfix-cli`), not binary names and not necessarily the directory basename.
**`workspace` MUST be ordered by ascending filesystem path of each crate’s `Cargo.toml`** — i.e. `sorted(crates/*/Cargo.toml)`.
For this repo the directories sort as `aa-graph` → `pnpmfix-cli` → `pnpmfix-core` → `zz-index`, so package names appear as `pnpmfix-graph`, then `pnpmfix-cli`, then `pnpmfix-core`, then `pnpmfix-index`.
Do **not** sort by package name, dependency-first order, or the `members` array (intentionally not path order).
Resolve `version.workspace` / `license.workspace` from `/app/Cargo.toml` `[workspace.package]`.

`bundles` MUST preserve `release_matrix.csv` row order.
`hold_count` is the number of artifacts whose `status` is `hold` (same as `totals.hold`), **not** the count of hold strings.
`checksums.sha256`: every regular file under `/app/dist` except itself, paths relative to dist, sorted by path, `digest␠␠rel` (exactly two spaces).
Smoke invocations must pass `--forbidden-hosts` and `--lane`.
