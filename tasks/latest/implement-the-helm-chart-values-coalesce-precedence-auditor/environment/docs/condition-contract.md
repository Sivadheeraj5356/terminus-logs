# Condition contract

A dependency `condition` is a dot-path into the **parent release values** evaluated after the parent chart has coalesced layers `defaults`, `parent` (empty for root), and all `--values` files — **before** any `--set` pairs.

Path lookup uses dot segments. Missing paths evaluate to `false`. Boolean false, empty string, integer zero, and null/absent all mean disabled.

When a condition evaluates false:

- The subchart manifest id is omitted from `active_charts`.
- No `values` entry is emitted for that subchart.
- Nested dependencies of the disabled subchart are not visited.

When true, the subchart directory `charts/<name>/` must exist or resolve fails with a non-zero exit and no output file.
