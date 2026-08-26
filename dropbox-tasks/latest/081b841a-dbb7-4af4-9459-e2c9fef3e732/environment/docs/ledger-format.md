# Ledger fixtures

## `/app/ledger/dependency_ledger.csv`

One row per dependency entering the build. Columns:

| Column | Values | Meaning |
|---|---|---|
| `name` | string | Package or model name (may contain `/`). |
| `ecosystem` | `npm`, `pypi`, `go`, `huggingface` | Source ecosystem. |
| `version` | string | Version or revision as pinned by the build. |
| `license` | SPDX id or `LicenseRef-*` | Declared license. |
| `channel` | `stable`, `beta`, `nightly` | Release channel of the pinned version. |
| `provenance` | `verified`, `unverified`, `absent` | Lockfile provenance state. |
| `lock_generation` | integer | Ledger generation the lockfile entry was written at (`0` when provenance is `absent`). |
| `scope` | `runtime`, `build`, `dev` | Where the dependency is used. |
| `origin` | `direct`, `transitive` | How the dependency entered the graph. |
| `install_scripts` | `true`, `false` | Whether the package runs install-time scripts (npm). |
| `artifacts` | `path=digest` pairs joined by `;`, or empty | Pinned registry artifacts (model dependencies only). Paths are relative to `/app/models/`. Digests are SHA-256, lowercase hex. |

## `/app/ledger/quarantine.csv`

The quarantine registry. Columns:

| Column | Values | Meaning |
|---|---|---|
| `kind` | `package`, `artifact` | What the entry pins. |
| `ecosystem`, `name` | strings | Set for `package` entries; empty otherwise. |
| `digest` | SHA-256 hex | Set for `artifact` entries; empty otherwise. |
| `status` | `active`, `lifted` | Whether the quarantine is currently in force. |
| `clause` | `QR-*` | Handbook clause that opened the quarantine. |

## `/app/ledger/meta.json`

Snapshot metadata: `ledger` (name), `generation` (current ledger generation,
integer), `snapshot` (RFC 3339 timestamp).
