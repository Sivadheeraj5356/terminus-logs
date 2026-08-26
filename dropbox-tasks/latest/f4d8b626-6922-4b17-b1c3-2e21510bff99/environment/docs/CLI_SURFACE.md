# CLI surface

Binary: /app/target/release/expeditctl

Subcommands:
1. ingest-dive-log --bundle PATH --policy PATH --staging PATH
2. resolve-precedence --staging PATH --output PATH
3. reconcile-observations --resolved PATH --output PATH
4. export-atlas --observations PATH --policy PATH --atlas PATH

export-atlas loads /app/state/{expedition_id}-resolved.json for dive_lanes per ATLAS_EXPORT.md and RESOLVED_ARTIFACTS.md.

Exit 0 on success. On failure print one token from ERROR_CODES.md to stderr and exit 1.
