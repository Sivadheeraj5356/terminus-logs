Go module emit rules for Composer / Phinx publication

checksum_sha256 comes from the unit checksum field after applying
checksum_peel_mode from the active cutover register. Ignore sibling fields such
as published_sum.

A replace matches only when old_path and old_version both equal the require
after +incompatible stripping. Which matching row wins is
replace_match_policy. replace_rules lists only directives that actually matched
an emitted edge.

Distinct (module_path, version) pairs each keep their own row. Drop a trailing
+incompatible wherever a version is stored on the published graph.

Digests serialize as compact JSON lock lines with sorted object keys, kind
exactly module, edge, or replace, is_root a JSON boolean, and literal slashes.
Sort encoded lines as whole strings before hashing. Companion checksum layout
follows digest_checksum_layout on the active register.
