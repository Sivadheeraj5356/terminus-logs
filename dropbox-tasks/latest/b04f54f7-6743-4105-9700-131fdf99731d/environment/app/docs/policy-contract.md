# Policy contract

`releasekit audit` accepts `--profile`, `--matrix`, `--components`, `--locks`, `--edges`, and `--out`. Component ordering and cycle semantics are normative in `advanced-graph-contract.md`. It emits policy checks in the exact order blocked_license, dev_policy, locked_versions, platforms, runtime_size, and keeps all warning reasons sorted instead of short-circuiting.

Only lock rows for the requested profile define the selected component set. Duplicate rows for the same profile and component use the last matching row as the effective audit lock; earlier rows remain only in packaged `share/locks.csv`. A lock whose component is absent from the component catalog is a ghost lock: emit `missing_component:<component>`, fail `locked_versions`, and exclude it from selected components, direct lock counts, and active dependency edges. A real component whose effective lock version differs from the component catalog version emits `version_mismatch:<component>:<lock_version>:<component_version>` and also fails `locked_versions`.

Duplicate catalog rows follow the parallel rule: the last `components.csv` row
for a component is the only effective metadata row, while all matching source
rows remain packaged. Active required edges to missing children emit
`missing_required_edge:<parent>-><child>` and fail `locked_versions`; optional or
inactive missing-child edges are silent. Conditional scopes and their nested
`cfg:` grammar are defined completely in `vcpkg-release-contract.md`. Active edge
source-row multiplicity is preserved in audit edge arrays, counts, and risk;
graph structure uses unique endpoint pairs as defined in `advanced-graph-contract.md`.

Runtime size is the sum of all included non-doc components. Risk score is `31 * warning_count + 3 * dev_component_count + 5 * critical_count + 2 * edge_count`, with an extra 13 when runtime size is over the limit. License and owner arrays are sorted unique lists.

`dev_dependency:<component>` warnings are emitted only for included `dev` components when the current matrix row has `allow_dev=false`; allowed dev components still count in `dev_component_count` and risk score but do not fail `dev_policy`.
