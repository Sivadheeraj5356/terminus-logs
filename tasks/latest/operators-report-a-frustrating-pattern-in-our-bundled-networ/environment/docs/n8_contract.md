# n8 observation contract

Profile label: `concurrency_ordering`

## Output path

`/app/output/n8_observations.json`

## Top-level schema

| field | type | notes |
|-------|------|-------|
| profile | string | always `concurrency_ordering` |
| rows | array of objects | one element per replay batch row |
| lane_digest | string | `0x` + 8 lowercase hex digits |

## Row schema

| field | type | notes |
|-------|------|-------|
| batch | string | batch id from replay driver |
| key | string | link key |
| gen | unsigned integer | generation counter |
| gate_code | string | single character (`A` accepted, `D` denied) |
| cfg_mask | unsigned integer | configured address mask |
| sample_mask | unsigned integer | listing/probe sample mask |
| live_mask | unsigned integer | live address probe mask |
| lane_digest | string | per-row digest (see below) |

## Gate rules

- Rows with `gate_code` `D` must have `cfg_mask`, `sample_mask`, and `live_mask` all zero.
- Accepted rows (`gate_code` `A`) must have all three mask columns equal and match the live probe reading for that key.

## lane_digest line format

Per-row digest:

```
lane_digest = fnv32(key bytes, gen, cfg_mask, sample_mask, live_mask, gate_code)
```

Render as `"0x"` followed by eight lowercase hex digits.

Bundle digest (`lane_digest` top-level field):

```
lane_digest = fnv32(concat of "batch:gen:cfg:sample:live:gate;" for each row in file order)
```

## Address mask encoding

Masks are unsigned 32-bit values representing host-order address payloads (for example `0x0a010101`).

## Cross-surface parity

After a documented replay sequence, configured listings, sample probes, and live probes must agree on accepted rows. Denied rows indicate stale or divergent state across those surfaces while reconciliation is still in flight.

## Carrier-down recovery

Fixture lines with `carrier=down` model a **transient** carrier-delay window, not a permanent denial. During replay the link may stay up while configuration advances; carrier polling must finish before teardown. Once the replay driver has polled through the carrier window and all three mask columns reconcile for a row, the emitted observation must classify it as Accepted (`gate_code` `A`). After carrier teardown the reconciled masks are zero and the row still remains Accepted. Rows that begin in a carrier-down posture must recover to accepted rows by the end of the documented replay sequence for that batch (for example `w03`/`r_row_c` and `w06`/`r_row_c2`).

Live address probes must reflect the address payload that was applied for that key and generation at observation time. Emit must report the live probe captured during replay, not a copy of the configured listing alone.
