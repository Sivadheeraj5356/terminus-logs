# Indigo Palisade Mediation Policy

## Semantic versions

Semantic versions are `major.minor.patch` with optional `-qualifier`; numeric fields compare numerically and qualifiers compare lexicographically after release versions.

## Version ranges

A version range `[a,b)` includes `a` and excludes `b`; `(a,b]` excludes `a` and includes `b`; `[a]` means exact `a`.

Candidate versions are versions present in `local_repo.edn` after relocation.

## Processing order

Apply relocation before exclusions, BOM constraints, version-range intersection, and graph traversal.

A dependency is ignored when its relocated coordinate is in any active exclusion set.

Optional dependencies are excluded unless they are roots or `optional-default` is true.

Scope propagation chooses the earlier scope in `scope-order`; dependencies with final scope outside `include-scopes` are excluded from `classpath.csv` but still appear in mediation when they influenced conflicts.

Nearest-wins depth is measured from roots after exclusions and optional pruning. Ties choose the highest version, then lexicographic coordinate.

BOM exact versions override requested ranges only when the exact version is inside the dependency range. If outside, use the highest available version in the intersection and report `bom_override_rejected`.

Classpath order is topological by selected dependency edges, then ascending depth, scope rank, coordinate, and version.

A cycle among selected artifacts is fatal as `dependency_cycle`.

## Worked example

If root A requests x:[1.0.0,2.0.0) at depth 1 and root B reaches x:1.8.0 at depth 2, x is mediated from A's nearer request. If the BOM pins x:1.9.0, that pin is used only when 1.9.0 is inside A's range; otherwise the nearest legal candidate remains and bom_override_rejected is reported.

## Reason and severity

| reason | severity | fatal? |
|---|---|---|
| `bom_override_rejected` | `warning` | no |
| `checksum_mismatch` | `warning` or `critical` from config | no when `:report`, yes when `:fatal` |
| `license_denied` | `error` | no |
| `license_unknown` | `warning` | no |
| `range_conflict` | `error` | no |
| `relocated_artifact` | `warning` | no |
| `scope_excluded` | `warning` | no |
| `dependency_cycle` | `critical` | yes |
| `duplicate_primary_key` | `critical` | yes |
| `invalid_version` | `critical` | yes |
| `invalid_range` | `critical` | yes |
| `relocation_cycle` | `critical` | yes |
| `schema_invalid` | `critical` | yes |
| `unknown_checksum_row` | `critical` | yes |
| `unresolved_required_artifact` | `critical` | yes |

Fatal reasons stop processing with nonzero exit and no output files. Reportable reasons allow exit zero and deterministic output files.

## Cross-output invariants

- `audit.summary.classpath_count` equals the number of data rows in `classpath.csv`.
- `audit.summary.selected_count` equals the number of data rows in `mediation.csv` with a nonempty `selected_version`.
- `audit.summary.finding_count` equals the number of data rows in `findings.csv`.
- Every `classpath.csv.coord` must appear in `mediation.csv` with the same selected version.
- Every nonzero `by_reason` count equals occurrences in `findings.csv` plus `reason_codes` occurrences in `classpath.csv` and `mediation.csv`.
- Reordering roots, repository map entries, BOM entries, checksums, and relocations without semantic changes must not change output bytes.
