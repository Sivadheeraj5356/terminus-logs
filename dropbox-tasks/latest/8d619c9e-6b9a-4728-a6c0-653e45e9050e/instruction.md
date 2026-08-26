# Desiccator tray registry replay

The stdlib-only Rust sources at `/app/desiccator_tray_src/` are a partial, broken tray-registry replay tool: they do not compile, and once they build the behavior still disagrees with the normative contract in `/app/task_file/schema.md` in more than one place. Repair the sources in place so they build and match that contract, then install the release binary at `/app/bin/desiccator_tray` (`/app/bin` is on `PATH`). `schema.md` is the source of truth for the field tables, per-op field profile, output shape, reject reasons, and the seed run's expected totals — read it in full and repair every deviation you find. Do not edit the schema or anything under `/app/task_file/`, and do not add `serde` or any other crate; emit the JSON by hand. Build offline:

```text
cd /app/desiccator_tray_src
CARGO_NET_OFFLINE=true cargo build --release
install -m 755 target/release/desiccator_tray /app/bin/desiccator_tray
```

## Run behavior

The CLI takes zero or one task-directory argument; with none it reads `/app/task_file` from any working directory (a copied tree such as `/tmp/tray_copy` must work identically). Two or more arguments is fatal. A fatal run exits nonzero with silent stdout/stderr and leaves any existing `/app/output/registry.json` bytes untouched. A successful run deletes and recreates `/app/output/`, writes only `registry.json`, stays quiet, is byte-identical on reruns, and never modifies the input task directory. Exit fatally, before writing output, when config or shard collection hits: a missing `trays.json` or `events/` directory; no lowercase `.tray` files under `events/`; invalid UTF-8 in any shard; or malformed `trays.json` (missing/empty `trays` roster or invalid numeric fields).

## Replay rules

Event shards are tab-separated `.tray` files under `events/`, five trimmed fields per line: `event_id`, `op`, `tray_id`, `units`, `lot_tag`. Recursively discover files whose extension is exactly lowercase `.tray`, normalize `\r\n`/bare `\r`/`\n`, sort shard paths lexicographically, and replay in file order; each non-blank line takes a zero-based discovery ordinal. Blank lines are skipped entirely. A line that is not exactly five fields takes an ordinal, appends it to `invalid_lines`, and counts in `total_lines`, but produces no `rejected_events` row.

Evaluate each parsed line against this precedence, first match wins:

`BAD_EVENT` → `DUPLICATE_EVENT` → `UNKNOWN_OP` → `UNKNOWN_TRAY` → `BAD_LINE` → `TRAY_LOCKED` → `TRAY_HELD` → `BAD_UNITS` → op-specific (`OVER_CAPACITY`, `UNDERFLOW`, `EMPTY_TRAY`, `REGEN_BLOCKED`, `BAD_STATE`).

`TRAY_LOCKED` blocks every op except `LOCK` and `UNLOCK` while `locked`. `TRAY_HELD` blocks `LOAD`, `UNLOAD`, `REGEN`, `SEAL`, `OPEN` while `held`, but not `LOCK`, `UNLOCK`, `HOLD`, `RELEASE`. Only successful applies reserve an `event_id`: a rejected line does not mark its id seen, so a later valid line with the same id may still apply; once an id has applied, further lines with that id emit `DUPLICATE_EVENT` and increment `duplicate_events` only, with no state change. The remaining op semantics (`REGEN` lower-tier gating, `LOAD`/`UNLOAD` bounds, `SEAL`/`OPEN` state rules) and every field type live in `schema.md`.

## Output

Write `/app/output/registry.json` as hand-written UTF-8 JSON with two-space indent, keys sorted at every object level, and a trailing newline. Top-level keys in sort order are `duplicate_events`, `invalid_lines`, `rejected_events`, `summary`, `trays`. The exact per-object key sets, field types, and the seed run's expected totals and anchors are defined in `schema.md`; treat it as authoritative.
