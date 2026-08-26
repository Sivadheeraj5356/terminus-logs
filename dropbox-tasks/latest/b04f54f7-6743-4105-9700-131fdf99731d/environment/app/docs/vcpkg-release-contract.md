# Release contract

`/app/scripts/release.sh` creates the complete offline release under `/app/dist`.
It must remove stale `/app/dist` output before rebuilding, build the Rust workspace
with `cargo build --release --locked --offline --bin releasekit`, and never require
network access. It runs from `/app` with `CARGO_NET_OFFLINE=true`.
Every bundled `bin/releasekit` is a byte-for-byte copy of the executable produced
by that Cargo release build. It is a Linux ELF whose first four bytes are
`0x7f`, `E`, `L`, `F`; scripts, wrappers, and proxy programs are not substitutes.

For every row in `/app/config/release_matrix.csv`, in matrix order, create:

- unpacked bundle directory `/app/dist/bundles/releasekit-<profile>`
- reproducible archive `/app/dist/releasekit-<profile>-linux-x86_64.tar.gz`

Do not hardcode the bundled profile or component names. A valid run uses the
current contents of `release_matrix.csv`, `components.csv`, `locks.csv`,
`dependency_edges.csv`, and `data/smoke_specs/`, including rows added after the
starter files were written.

The only unpacked bundle directories live under `/app/dist/bundles`; do not also
write `releasekit-<profile>` directories at the root of `/app/dist`.

## Bundle layout

Each bundle contains exactly these regular files (plus their necessary parent
directories), with no additional regular files:

- `bin/releasekit`
- `share/release_matrix.csv`
- `share/components.csv`
- `share/locks.csv`
- `share/dependencies.csv`
- `share/policy.json`
- `share/run-smoke.sh`
- `share/audit-preview.json`
- `share/smoke_specs/<profile>.csv`
- `LICENSES.txt`
- `VERSION`

All release inputs copied into a bundle go under `share/`, not under `config/`.
`share/release_matrix.csv` in every bundle is an unfiltered, verbatim
byte-for-byte copy of the complete current `/app/config/release_matrix.csv` read
during that rebuild. It contains every live row in current matrix order; it is
never profile-filtered and must not come from an earlier cached snapshot. The
component, lock, and dependency CSVs are filtered for the current profile. The
source dependency file is named `/app/config/dependency_edges.csv`,
but the packaged filtered file must be named `share/dependencies.csv`.

`share/policy.json` has keys in this exact order: `profile`, `channel`,
`target`, `feature_set`, `max_runtime_kb`, `allow_dev`, `blocked_license`.

`share/components.csv` contains only components locked for that profile, ordered
by the source `/app/config/components.csv` order. If a component name occurs
more than once in `components.csv`, every matching row remains in the packaged
CSV, but the last source row for that component is the sole effective catalog
row for audit fields, version checks, policy warnings, topology, totals,
license/owner summaries, and `LICENSES.txt`. Earlier component rows never
contribute a second component or stale metadata. `share/locks.csv` contains only
rows for that profile, preserving every matching source row. If the same profile
and component appears more than once in `locks.csv`, the last matching row is
the effective lock row for audit component fields, version checks, dependency
selection, manifest metrics, and summaries; earlier duplicate rows remain only
in the packaged `share/locks.csv`. A lock row whose component is absent from
`components.csv` is a ghost lock: preserve it in `share/locks.csv`, emit one
`missing_component:<component>` warning per missing component name, fail
`locked_versions`, and exclude it from `share/components.csv`, the audit
`components` array, `direct_lock_count`, and active dependency edges.
`share/dependencies.csv` contains rows whose `profile` is `*` or the current
profile; optional dependency edges are reported by the audit only when both
endpoints are locked for that profile.
All filtered CSVs keep the source header and the source row order for rows that
survive filtering.

`LICENSES.txt` is not full license text. It contains only the sorted unique
license identifiers for the components included in that bundle, one identifier
per line, with no extra prose. If a bundle has no included components, write
`LICENSES.txt` as a zero-byte file: do not write a blank line.

`VERSION` contains the live workspace package version followed by exactly one
LF, currently `0.7.0\n`. If the workspace version and matching local-package
entries in `Cargo.lock` change together, every `VERSION`, binary version, and
manifest crate/package version follows that new value on the next rebuild.

## Smoke script

`share/run-smoke.sh` must be POSIX shell with the first line exactly:

```sh
#!/bin/sh
```

Do not use a bash shebang. The script is invoked as:

```sh
sh share/run-smoke.sh <output-json-path>
```

It must run the packaged binary at `../bin/releasekit` relative to the script's
bundle directory, not `/app/target`, and write the audit JSON to the requested
output path. If `<output-json-path>` is omitted, the script writes
`audit-<profile>.json` in the bundle root directory. Resolve all bundled inputs
and the binary from the script's own location, not the caller's working
directory. This must work after relocation to a path containing spaces while
`/app/target`, `/app/dist`, and `/app/config` are unavailable. An explicit
nested output path may also contain spaces; create all missing parent
directories and write only that requested file.

## `releasekit` CLI

The packaged binary prints `releasekit <workspace-version>` plus one LF for
`--version` (therefore exactly `releasekit 0.7.0` with the starter workspace).
It must also support:

```sh
releasekit audit --profile <profile> --matrix <csv> --components <csv> --locks <csv> --edges <csv> --out <json>
```

The direct audit CLI output must match the bundle's `share/audit-preview.json`.
Every generated JSON file—`policy.json`, `audit-preview.json`, direct `--out`,
and `release-manifest.json`—ends with exactly one trailing LF byte and not two. The audit CLI
creates missing parent directories for the requested `--out` path.
If a supported flag is supplied more than once, use the final value for that
flag. For example, `--profile old --profile new` audits `new`, and
`--out first.json --out second.json` writes only `second.json`.

## Audit preview JSON

`share/audit-preview.json` is pretty or compact JSON, but object keys must appear
in this top-level order, with `totals` last:

1. `profile`
2. `target`
3. `channel`
4. `feature_set`
5. `max_runtime_kb`
6. `allow_dev`
7. `components`
8. `dependency_edges`
9. `license_summary`
10. `owners`
11. `policy_checks`
12. `warnings`
13. `totals`

Top-level value types:

- `profile`, `target`, `channel`, and `feature_set` are strings from the matrix.
- `max_runtime_kb` is an integer from the matrix.
- `allow_dev` is a boolean from the matrix: the exact case-sensitive values
  `true`, `yes`, and `1` are true, and every other value is false.
- `components`, `dependency_edges`, `license_summary`, `owners`,
  `policy_checks`, and `warnings` are arrays.
- `totals` is an object.

Each component object has exactly the data needed by the audit contract:

- `name`: component name from locks/components
- `version`: version from `components.csv`
- `kind`: component kind from `components.csv`
- `license`: license identifier from `components.csv`
- `critical`: boolean, true when `critical` is `yes`, `true`, or `1`, case-insensitive
- `size_kb`: integer from `components.csv`
- `checksum`: profile lock checksum
- `source`: profile lock source path
- `direct`: boolean `true`

Component order is dependency-parent before child over the SCC condensation
DAG, with deterministic lexicographic tie-breaks. Cycles are reported one
warning per cyclic strongly connected component; independent cycles and
acyclic descendants are never merged. Self-loops are cyclic one-node SCCs.
The complete ordering, graph-projection, and cycle rules are normative in
`advanced-graph-contract.md`.

`dependency_edges` is a sorted array of strings:

```text
<parent>-><child>:<relation>
```

It includes active applicable `*` and profile-specific edges only when both endpoints
are locked in this profile. Optional doc edges such as
`config-pack->docs-pack:documents` count only for profiles that lock `docs-pack`.
Different applicable relation rows between the same parent and child are
separate audit edges: keep one `parent->child:relation` string per relation row,
count each in `edge_count`, and include each in risk scoring.
If two applicable source rows render to the exact same edge string, such as a
global `*` row and a profile-specific row with the same parent, child, and
relation, preserve both rendered strings in `dependency_edges` and count both.
This is source-row multiplicity: exact duplicate rows from the same profile are
also preserved. Every active source row contributes one rendered edge string,
one `edge_count`, and its risk-score contribution. Topological graph structure,
however, uses one arc per unique `(parent, child)` pair, regardless of duplicate
rows, relations, or scopes. Edge strings are sorted but never deduplicated.

The `scope` column controls activation. Empty scope and the legacy values `all`,
`runtime`, `data`, `doc`, and `dev` are unconditional. Other simple scopes are
`&`-joined clauses: `feature:<token>`, `target:<exact-target>`, or
`channel:<exact-channel>`. A leading `!` negates a clause. Feature matching uses
exact nonempty `+`-separated tokens from `feature_set`, never substrings.

A nested scope begins with `cfg:` and uses the same non-negated atoms inside
recursive `all(expr,...)`, `any(expr,...)`, and `not(expr)` operators. The
`all` and `any` operators require at least one operand. For example:

```text
cfg:all(feature:signed,any(target:linux-x86_64,target:linux-arm64),not(channel:stable))
```

Because nested forms contain commas, their CSV field is quoted. Scope matching
does not fold case or trim whitespace. An unknown clause or malformed expression
evaluates false. Inactive rows remain in packaged `share/dependencies.csv` but
do not affect ordering, edge strings, warnings, totals, or risk.

When an active non-optional row has a selected parent and an unselected child,
omit its edge string and emit `missing_required_edge:<parent>-><child>`. Repeated
rows can request the same warning, but warnings are sorted unique. Missing
optional children and all inactive missing-child rows are silent. The `optional`
field is true only for the exact case-sensitive values `yes`, `true`, and `1`;
all other values are false.

`license_summary` and `owners` are sorted unique arrays for included components.

`policy_checks` is always emitted in this exact order:

1. `blocked_license:<ok|fail>`
2. `dev_policy:<ok|fail>`
3. `locked_versions:<ok|fail>`
4. `platforms:<ok|fail>`
5. `runtime_size:<ok|fail>:<runtime_kb>/<max_runtime_kb>`

`locked_versions` is `fail` when any included component's effective lock
version differs from the catalog version, or when any ghost lock produced a
`missing_component:<component>` warning, or when an active required edge produced
a `missing_required_edge` warning. A single
`version_mismatch:<component>:<lock_version>:<component_version>` warning is
therefore enough to make the third policy check `locked_versions:fail`.

Warnings are sorted unique strings. Supported warning prefixes are
`blocked_license`, `dev_dependency`, `platform`, `version_mismatch`,
`missing_component`, `missing_required_edge`, `dependency_cycle`, and
`runtime_size`. Use these exact
payload formats:

- `blocked_license:<component>:<license>`
- `dev_dependency:<component>`
- `platform:<component>:<target>`
- `version_mismatch:<component>:<lock_version>:<component_version>`
- `missing_component:<component>`
- `missing_required_edge:<parent>-><child>`
- `dependency_cycle:<component>|<component>` for each cyclic strongly connected
  component, with only that SCC's names sorted and pipe-delimited; a selected
  self-loop emits `dependency_cycle:<component>`
- `runtime_size:<runtime_kb>:<max_runtime_kb>`

The `runtime_size` warning uses colons between both sizes, while the
`runtime_size` policy check uses a slash in its final payload. Do not
short-circuit after the first warning. Emit `dev_dependency:<component>` only
when the included component has kind `dev` and the current matrix row has
`allow_dev=false`; when `allow_dev=true`, the dev component still contributes to
`dev_component_count` and risk score but produces no dev warning.

`totals` has these fields in this exact order:

- `component_count`
- `direct_lock_count`
- `runtime_kb`
- `critical_count`
- `license_count`
- `dev_component_count`
- `edge_count`
- `policy_pass`
- `risk_score`

`runtime_kb` is the sum of included non-doc component sizes. `policy_pass` is
true only when there are no warnings. `risk_score` is:

```text
31 * warning_count
+ 3 * dev_component_count
+ 5 * critical_count
+ 2 * edge_count
+ 13 when runtime_kb is over the matrix max_runtime_kb, otherwise 0
```

## Release manifest

`/app/dist/release-manifest.json` has top-level keys exactly:

1. `format_version`
2. `package`
3. `workspace`
4. `bundles`

`format_version` is the integer `1`, not the string `"1"`.

For the starter workspace, `package` is exactly:

```json
{"name":"releasekit-cli","version":"0.7.0","target":"x86_64-unknown-linux-gnu"}
```

The name comes from the CLI crate, the version is its live resolved workspace
version, and the target is the current `rustc -vV` host. A coordinated workspace
version mutation changes only the version value in this shape.
This package target is independent of matrix targets. Every bundle entry's
`target`, its policy, and its audit use that profile's exact matrix `target`.

`workspace` is an array of crate metadata objects, not plain strings. It lists
these objects in this exact order: `releasekit-cli`, `releasekit-core`, then
`releasekit-table`. Each object has keys in this order: `name`, `version`,
`license`, `dependencies`. The expected entries are:

```json
[
  {"name":"releasekit-cli","version":"0.7.0","license":"Apache-2.0","dependencies":["releasekit-core"]},
  {"name":"releasekit-core","version":"0.7.0","license":"Apache-2.0","dependencies":["releasekit-table"]},
  {"name":"releasekit-table","version":"0.7.0","license":"MIT","dependencies":[]}
]
```

Names, licenses, dependency arrays, object key order, and member order remain as
shown. Resolve each entry's `version` independently from that member's live
`Cargo.toml`. An explicit member declaration such as `version = "0.7.8"` wins
for that member only. A declaration `version.workspace = true` inherits
`workspace.package.version` from the root manifest. Never copy one resolved
member version into the other workspace entries. The top-level package version,
the bundled `VERSION` files, and `releasekit --version` use the independently
resolved `releasekit-cli` version; changing only another member does not change
those values. Every changed local package version must have its matching
`Cargo.lock` entry changed so the locked offline build remains valid.

`bundles` follows release matrix order. Each bundle entry includes:

- `profile`
- `channel`
- `target`
- `archive`
- `archive_sha256`
- `binary_sha256`
- `policy_sha256`
- `audit_preview_sha256`
- `component_count`
- `runtime_kb`
- `edge_count`
- `risk_score`

The count and score fields must mirror the matching bundle's
`audit-preview.json` `totals`. Hash fields are SHA-256 values computed after all
files and archives are final.

## Checksums and archives

`/app/dist/checksums.sha256` lists every regular file below `/app/dist` except
`checksums.sha256` itself. Paths are relative to `/app/dist` and sorted
lexicographically.

Each archive's first member is an explicit tar directory entry (type `5`) named
exactly `releasekit-<profile>`; this is a real member, not merely a prefix on file names.
It is the one root directory, and archive file paths match the corresponding
unpacked bundle file paths. Archives must be
reproducible across reruns from unchanged inputs, with member paths sorted in
bytewise/ASCII order across files and directories together, not grouped by type,
and normalized tar metadata: uid `0`, gid `0`, and mtime
`2026-01-01T00:00:00Z`. Archive modes are normalized too: directories are
`0755`, executable regular files are `0755`, and non-executable regular files
are `0644`. The executable regular files in every bundle are exactly
`bin/releasekit` and `share/run-smoke.sh`; JSON, CSV, `VERSION`, and
`LICENSES.txt` members must not carry executable bits.

The unpacked bundles use the same modes regardless of the caller's umask:
directories, `bin/releasekit`, and `share/run-smoke.sh` are `0755`; every other
regular file is `0644`.

## Dynamic rebuild inputs

Matrix, component, lock, dependency, and smoke-spec records are dynamic and may
be added, removed, duplicated, reordered, or replaced. Current inputs may use
any documented quoted CSV, scope, graph, duplicate-row, or member-version form.
Every run uses current files, removes the previous `dist` tree entirely, and
leaves no stale bundle, archive, checksum row, or manifest entry. Restoring
identical inputs and rebuilding must restore byte-identical output files.

A bundle is relocatable: its smoke script continues to work from a copied bundle
after `/app/target` and `/app/dist` are unavailable, because every input and the
executed binary are resolved within that bundle.
