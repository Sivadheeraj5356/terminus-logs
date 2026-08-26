# Coordination trace contract

This document defines the public formulas and JSON schema for `/app/output/coordination_trace.json`. Digest prefixes use `sha256sum` over the documented byte strings (first 16 hex characters).

## Output schema

Top-level envelope:

| Field | Type | Description |
|-------|------|-------------|
| `runs` | array | One row per matrix row from `matrix_order.txt` |
| `report_digest` | string | 16-hex digest over canonical row envelopes |
| `replay_token` | string | 16-hex digest binding workspace to `report_digest` |

Each run row:

| Field | Type | Description |
|-------|------|-------------|
| `scenario` | string | Matrix row identifier |
| `slice_epoch` | int | Active slice counter after the scripted cycle |
| `marker_fp_host` | string | Host layered-view fingerprint |
| `marker_fp_peer` | string | Peer layered-view fingerprint |
| `hold_gap` | int | `host_visible - peer_new_bytes` |
| `staging_lag` | int | `staging_bytes - journal_cursor` |
| `checkpoint_epoch` | int | Published checkpoint sidecar epoch |
| `lineage_token` | string | Generation lineage binding digest |
| `preservation_stamp` | string | Archival body stamp for the active slice |
| `row_seal` | string | Per-row integrity seal |

## Marker fingerprint

```
marker_fp_host = hex(sha256("host|" + host_view_bytes))[0:16]
marker_fp_peer = hex(sha256("peer|" + peer_view_bytes))[0:16]
```

## Hold gap

```
host_visible = byte length of views/host/slot.dat
peer_new_bytes = admitted peer bytes for the active slice
hold_gap = host_visible - peer_new_bytes
```

When authorities agree after coordinated repair, `hold_gap` is zero for every matrix row.

## Staging lag

```
staging_lag = len(journal/staging.log) - int(journal/cursor)
```

After a coordinated flush and gate open, `staging_lag` is zero for every matrix row.

## Checkpoint epoch

The published sidecar `published/checkpoint_epoch` must equal the row `slice_epoch` after repair.

## Lineage token

```
lineage_token = hex(sha256(str(parent_gen) + "|" + journal_committed_body + latch_state))[0:16]
```

`parent_gen` is the generation before the final slice close for the scenario. `journal_committed_body` is the durable journal file. `latch_state` is the raw `gate/latch` file bytes.

## Body stamp

```
preservation_stamp = hex(sha256(str(slice_epoch) + "|" + fixture_body))[0:16]
```

`fixture_body` is the raw bytes of `fixtures/cycle/gen{N}/workspace.dat` for the row's `slice_epoch`.

## Row seal

Canonical row pipe-fields in order:

```
scenario|slice_epoch|marker_fp_host|marker_fp_peer|hold_gap|staging_lag|checkpoint_epoch|lineage_token|preservation_stamp
```

```
row_seal = hex(sha256(canonical_row))[0:16]
```

## Report digest

For each row, build a canonical fragment:

```
scenario;slice_epoch;marker_fp_host;marker_fp_peer;hold_gap;staging_lag;checkpoint_epoch;lineage_token;preservation_stamp;row_seal
```

Sort fragments lexicographically, join with newline, then:

```
report_digest = hex(sha256(joined_fragments))[0:16]
```

## Replay token

```
replay_token = hex(sha256(report_digest + "|" + workspace_root))[0:16]
```

## Idempotency rule

Two consecutive state-audit replays on an unchanged workspace tree must yield identical `report_digest` and `replay_token`.

## Matrix completion (after coordinated repair)

When authorities agree across the scripted matrix in `matrix_order.txt`:

- `hold_gap` and `staging_lag` are zero for every matrix row.
- `checkpoint_epoch` equals `slice_epoch` for every row.
- `slice_once` finishes at `slice_epoch` 1.
- `slice_twice`, `recycle_trap`, `warm_resume`, and `staggered_width` finish at `slice_epoch` 2 after their scripted close.
- `preservation_stamp` matches the body-stamp formula for each row's `slice_epoch`.

## Gate and journal ordering

Publication to layered views must occur only after `journal` flush completes and the generation `gate` latch opens. Reload notifications must not copy published bodies ahead of that ordering.
