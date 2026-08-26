Go module qualification for the Iris Composer cutover

The published graph is the dependency closure of the gateway root from
export_meta — only units reached by walking direct requires after local replace
resolution belong in it. Entries that merely sit in module_index without being
reached are not package units.

When a version block lists several units, take the one whose path equals the
module being visited. Nested command units are not substitutes. Record
go_version from the version block.

Scaffolding, replace scan direction, and when retract/exclude apply relative to
replace are controlled by the active cutover register tokens (see volume-3). A
matched replace still records edge_kind replace even when only the version
changed on the same module path.

Only export_meta, retract_queue, exclude_queue, and module_index feed the
resolved set.
