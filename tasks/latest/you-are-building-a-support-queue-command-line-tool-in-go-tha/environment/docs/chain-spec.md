# HMAC Audit Chain Specification

## Overview

Every resolved ticket appends one entry to the global `resolution_chain` table. The entries form a singly-linked list ordered by `chain_id ASC`, secured with HMAC-SHA256.

## Parameters

- **HMAC key:** value of the `HMAC_SECRET` environment variable. If `HMAC_SECRET` is not set, fall back to the default value `support-queue-secret-2026`.
- **Algorithm:** HMAC-SHA256, output encoded as lowercase hexadecimal string (64 chars)

## Data String Format

```
<chain_id>|RESOLVE|<ticket_id>|<agent_id>|<resolution_minutes>|<sla_met>|<resolved_at>|<prev_hash>
```

Field definitions:

| Field               | Type    | Notes                                    |
|---------------------|---------|------------------------------------------|
| chain_id            | integer | The AUTOINCREMENT primary key of this row |
| ticket_id           | string  | Ticket identifier                        |
| agent_id            | string  | Agent identifier                         |
| resolution_minutes  | integer | Floor of elapsed seconds / 60            |
| sla_met             | string  | Literal `"true"` or `"false"`            |
| resolved_at         | string  | SQLite datetime string (UTC)             |
| prev_hash           | string  | `current_hash` of the previous entry, or `""` for the first |

## Chain Rules

1. The first entry has `prev_hash = ""` (empty string).
2. Each subsequent entry has `prev_hash` equal to the `current_hash` of the immediately preceding row (ordered by `chain_id ASC`).
3. `current_hash` is computed as: `HMAC-SHA256(key, data_string)` where `data_string` uses the fields above.
4. The `chain_id` used in the data string is the value assigned by SQLite AUTOINCREMENT at insert time.

## Verification

To verify the chain, iterate rows in `chain_id ASC` order. For each row:

1. Check that `prev_hash` equals the `current_hash` of the previous row (or `""` for the first).
2. Recompute the expected hash from the underlying data of that `resolution_chain` row — i.e. that row's own stored `chain_id`, `ticket_id`, `agent_id`, `resolution_minutes`, `sla_met`, `resolved_at`, and `prev_hash` field values, assembled into the data string above and re-hashed. Verification does **not** re-query the `tickets` or `resolutions` tables — it recomputes independently from the chain row's own underlying field data rather than simply trusting the already-stored `current_hash` value at face value.
3. Compare the freshly-recomputed hash with the stored `current_hash`.

Any mismatch indicates tampering of that row or a predecessor. (Separately, `resolve-ticket` itself is responsible for deriving `resolution_minutes` and `sla_met` correctly from the ticket's real `opened_at`/`resolved_at` timestamps and priority SLA threshold at write time — see instruction.md — so that what ends up "underlying" each chain row is already accurate; `chain-verify` does not redo that derivation.)
