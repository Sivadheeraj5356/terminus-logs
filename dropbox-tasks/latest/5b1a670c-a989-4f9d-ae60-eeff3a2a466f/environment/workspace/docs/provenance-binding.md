Iris Go-module cutover binding (Composer / Phinx)

Path bindings come from /workspace/config/paths.json. Authoritative keys for a
paths file include schema_version, proxy_export, cutover_register, sqlite_path,
digest_path, and checksum_path. Other keys (legacy_proxy_export,
legacy_cutover_register, database_path, phinx_sqlite_name, archive under
/workspace/data/archive/) are historical or smoke mirrors.

schema_version on the resolved graph comes from paths.schema_version. Root
identity is export_meta.root_module / root_version. Walk module_index from that
root; other top-level export maps such as shadow_index are not part of the
resolved set. go_version on each module row comes from the version block, not a
go_version nested on a unit.

Normalize policy tokens live in the cutover register referenced by
cutover_register. Token meanings are in
/workspace/docs/module-cutover-policy/volume-3-register-tokens.md.

edge_kind is require or replace. An edge is replace when a replace directive
matched the require being walked.

Migrate lands SQLite at the --paths sqlite_path for that run (not the checked-in
phinx.php smoke default) with tables:

module_units: module_path, version, checksum_sha256, go_version, is_root
module_edges: parent_path, parent_version, child_path, child_version, edge_kind
replace_rules: scope_path, scope_version, old_path, old_version, new_path, new_version

Sort modules by (module_path, version), edges by (parent_path, parent_version,
child_path, child_version, edge_kind), and replace_rules by (scope_path,
scope_version, old_path, old_version).

Release digests are compact JSON lock lines with sorted keys; kind is exactly
module, edge, or replace (never replace_rule); is_root is a JSON boolean and
slashes stay literal. Checksum file layout follows digest_checksum_layout from
the active cutover register.
