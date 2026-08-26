# The dyeworks tool is a command-line reader at /app/environment/dyeworks that par

- **UUID:** `61f6d0fd-74f9-480f-9c52-befa30a93887`
- **Slug:** `the-dyeworks-tool-is-a-command-line-reader-at-app-environmen`
- **Category:** security
- **Difficulty:** hard

## Summary

The dyeworks tool is a command-line reader at /app/environment/dyeworks that parses a compiled dyeworks-tree container and prints a one-line JSON summary for a file that conforms to the format. The summary is one line carrying exactly these keys in this order and nothing else: `version`, `dyeworksdefs_defined`, `nodes_parsed`, `lots_resolved`, `indirects_resolved`, and `root_type`, where `version` is the unit format version, `dyeworksdefs_defined` is the count of type declarations, `nodes_parsed` is the number of non-null nodes, `lots_resolved` and `indirects_resolved` are the counts of resolved lot references and indirect forms, and `root_type` is the type name of the root node.

The byte layout is documented in /app/environment/docs/dyeworks-format.md. Every file under /app/environment/testdata/valid conforms to the format, and each must keep parsing and printing the same summary, with the same keys, order, and values.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
