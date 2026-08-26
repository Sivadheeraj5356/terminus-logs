# Cycle report contract

Operator export for HA failback on the configured pair. The floating endpoint
must not be advertised until neighbor replay completes for the returned
generation.

The operator export `/app/output/wp_report.json` is produced only through
`vivostep emit -o /app/output/wp_report.json` after running scenarios with
`vivostep run`.

## Top-level fields

| field | type | meaning |
|-------|------|---------|
| `cycles` | array | completed cycle records |
| `surfaces` | array | per-authority measurements |
| `record_digest` | string | lowercase hex SHA-256 digest |

## `cycles[]`

Each element contains:

| field | type | meaning |
|-------|------|---------|
| `cycle_id` | string | scenario cycle identifier (see cold boot vs maintenance return below) |

#### Cold boot (`vivostep run --scenario wp-maint --cold`)

Each cold boot appends one completed cycle with `cycle_id` exactly `cold-boot`.
The record must include `epoch_pairs` and `gate_timings` for both
`neighbor_replay` and `endpoint_attach`, with strictly positive completion
ticks and neighbor replay strictly before endpoint attach.

#### Maintenance return (non-cold `vivostep run --scenario wp-maint`)

Each maintenance return appends one completed cycle with `cycle_id` exactly
`wp-maint`, including repeated returns within one session (do not suffix or
uniquify per epoch). The record must satisfy the same `epoch_pairs`,
`gate_timings`, and ordering rules as cold boot cycles.
| `gate_timings` | array | phase completion ticks |
| `epoch_pairs` | array | forward vs journal epoch coupling |

### `gate_timings[]`

| field | type | meaning |
|-------|------|---------|
| `phase` | string | phase label (`neighbor_replay`, `endpoint_attach`) |
| `completed_at_tick` | number | simulation tick when the phase finished |

### `epoch_pairs[]`

| field | type | meaning |
|-------|------|---------|
| `forward_epoch` | number | epoch observed on the forwarding authority |
| `journal_head_generation` | number | head generation on the durable journal |

After each completed cycle, `forward_epoch` must equal `journal_head_generation`.

## Session history

`vivostep run` appends completed cycle records to the operator session. Each
emitted report reflects the full accumulated history for that session, not only
the latest invocation. A `--cold` invocation followed by one maintenance return
in the same session must leave at least 2 completed cycles in `cycles` (one
`cold-boot`, one `wp-maint`).

## Cross-run epoch progression

When `vivostep run --scenario wp-maint` is invoked repeatedly without
`vivostep reopen`, each new maintenance return must derive its generation from
the persisted journal head and advance it. The final forward epoch and journal
head in the exported report must increase across such consecutive runs, and the
`cycles` array must grow by one completed record per additional maintenance
return. When two maintenance-return exports are compared from the same session
without an intervening reopen, the later export's `cycles` length equals the
earlier export's length plus one (len(cycles) + 1).

After `vivostep reopen`, stale journal generations below the active forwarding
epoch must be removed from persisted journal state before the next maintenance
return. Subsequent runs must again satisfy per-cycle epoch agreement, gate
ordering, and the cross-run progression rules in this section.

When `VIVO_SCHED_SEED` is set to each integer from 1 through 7 on otherwise
identical cold-plus-maintenance runs, at least 3 distinct `record_digest`
values must appear while the invariants in this document still hold.

## `surfaces[]`

| field | type | meaning |
|-------|------|---------|
| `name` | string | authority label (`forward`, `journal`) |
| `epoch` | number | current epoch on that authority |
| `last_event_tick` | number | tick of the latest recorded event |

## Persisted journal

`/app/data/journal.json` stores durable journal state as JSON with an
`entries` array of generation records. After `vivostep reopen`, stale journal
`entries` below the active forwarding epoch must be removed before the next
maintenance return.

## `record_digest`

Lowercase hexadecimal SHA-256 over the UTF-8 bytes of the canonical compact JSON
object containing only `cycles` and `surfaces`; `record_digest` itself is not
included in the hash input. The digest is sha256sum-compatible lowercase hex.
The compact JSON uses `,` and `:` separators with no added spaces or trailing
newline.

Canonical array ordering is:

- `cycles` sorted by `cycle_id` ascending.
- Each cycle's `gate_timings` sorted by `phase` ascending.
- Each cycle's `epoch_pairs` kept in the order emitted for that cycle.
- `surfaces` sorted by `name` ascending.

Canonical object key order is the report generator's emitted order:

- Top-level digest payload: `cycles`, then `surfaces`.
- `cycles[]`: `cycle_id`, `gate_timings`, `epoch_pairs`.
- `gate_timings[]`: `phase`, `completed_at_tick`.
- `epoch_pairs[]`: `forward_epoch`, `journal_head_generation`.
- `surfaces[]`: `name`, `epoch`, `last_event_tick`.

## Ordering rule

For every completed cycle, both phase completion ticks in `gate_timings` must
be strictly greater than zero. Neighbor replay must finish before endpoint
attach: the `neighbor_replay` tick must be strictly less than the
`endpoint_attach` tick.

## Examine output

`vivostep examine --surface dual` prints JSON with a `surfaces` array using
the same per-authority shape as the report.
