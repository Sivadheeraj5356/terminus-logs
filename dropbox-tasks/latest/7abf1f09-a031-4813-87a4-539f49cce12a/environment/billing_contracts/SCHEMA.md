# Chargeback ledger schema

Data layout for `/app/carrydown_engine` reading `/app/pledge_inputs` and writing `/app/output/ledger.json`. Monetary fields are integer micro-cent counts. Integer JSON tokens only (never floats) for microcent and unit fields.

## Input files under /app/pledge_inputs

| File | Contents |
|------|----------|
| config.json | Run configuration |
| tenants.json | Tenant roster |
| rate_cards.ndjson | Rate card rows |
| commitments.ndjson | Commitment rows |
| credits.ndjson | Credit rows |
| shared_pools.json | Shared pool definitions |
| usage_shards.json | Manifest of usage NDJSON shard filenames |

Each filename in `usage_shards.json` `usage_shard_files` is a separate NDJSON file in `/app/pledge_inputs`. The engine reads `usage_shards.json` and loads every listed shard. Each shard filename appears as a Go double-quoted string literal in engine sources alongside the manifest read.

Inputs and `/app/billing_contracts` are read-only; leave them byte-identical to the image baseline. Paths under `/app` are absolute ordinary directories (no work symlinks for pledge_inputs, billing_contracts, output, carrydown_engine, or the rebuilt binary).

## config.json

```json
{
  "billing_period": {
    "period_id": "string",
    "start_inclusive": "RFC3339 timestamp",
    "end_exclusive": "RFC3339 timestamp"
  },
  "currency": "string",
  "micro_cents_per_usd": "integer",
  "precedence": ["string", "..."],
  "remainder_tie_break": "string",
  "ledger_sort": ["string", "..."],
  "line_item_order": ["string", "..."],
  "digest_algorithm": "string",
  "schema_version": "integer"
}
```

Billing-period usage filter is half-open: `start_inclusive <= event_timestamp < end_exclusive` via `validate.go` `filterPeriod`.

`precedence` is applied in listed order from `config.json` against a running subtotal. Cap each reduction at the remaining balance. On-demand is residual after listed reductions.

`ledger_sort` tokens select tenant array order. Bundled tokens: `total_charge_microcents` descending, then `tenant_id` ascending. `report_digest` rows follow that tenant array order.

`line_item_order` is the service emission order. Omit services with zero units. Active tenants with no in-period usage appear with an empty `line_items` array. Omit inactive tenants entirely.

## tenants.json

```json
{
  "tenants": [
    {
      "tenant_id": "string",
      "name": "string",
      "region": "string",
      "active": "boolean (optional)"
    }
  ]
}
```

Tenant ledger rows omit input-only fields such as `region` and `active`. When `active` is omitted from roster input, the tenant is treated as active.

## Usage event row (NDJSON)

`event_id`, `tenant_id`, `service`, `timestamp`, `units` (integer)

Within each tenant/service walk, sort events by timestamp ascending, then `event_id` ascending (lexicographic). That encounter order drives commitment burn.

## Rate card row (NDJSON)

`rate_id`, `service`, `scope`, `scope_key`, `unit_rate_microcents`, `effective_from`, `effective_until`

`scope` is one of `global`, `region`, or `tenant`.

Active rate windows are half-open: `effective_from <= event_timestamp < effective_until`.

Scope precedence is narrowest wins: tenant over region over global. When multiple cards share the same winning scope and are active for the event, keep the first matching card in file order.

## Commitment row (NDJSON)

`tenant_id`, `period_id`, `service`, `committed_units`, `discount_rate_microcents`

Walk each service's usage events in the sort order above. Track one running remaining pledge balance for the tenant/service period; initialize from `committed_units` once, then decrement after each event.

Per-event committed discount microcents use that event's resolved `unit_rate_microcents`: `committed_units_at_event × (unit_rate_microcents − discount_rate_microcents)`.

## Credit row (NDJSON)

`credit_id`, `tenant_id`, `period_id`, `amount_microcents`

Sum credits whose `period_id` equals the billing period per tenant before precedence.

## shared_pools.json

```json
{
  "pools": [
    {
      "pool_id": "string",
      "period_id": "string",
      "total_cost_microcents": "integer",
      "participants": ["tenant_id", "..."]
    }
  ]
}
```

Allocate every period-matching pool with largest-remainder proportional split. Weights are each participant's net usage microcents after credit/commitment precedence. Clamp negative weights to zero. If all weights are zero, use equal weight `1` per participant. Remainder ties follow `remainder_tie_break` from config (`tenant_id_asc`). `pool_unallocated_microcents` is `0` when the full pool total is distributed. Shared amounts from multiple pools sum per tenant.

Tenant `total_charge_microcents` is `net_usage_microcents + shared_allocated_microcents`.

## ledger.json root

Keys in order: `period_id`, `currency`, `tenants`, `summary`, `report_digest`

Ledger root contains only those keys.

`report_digest` is lowercase hexadecimal SHA-256 (`digest_algorithm` `sha256`).

Digest UTF-8 payload is one pipe row per tenant in ledger tenant-array order, each ending with newline:

`tenant_id|total_charge_microcents|net_usage_microcents|shared_allocated_microcents\n`

Exactly four fields per row. Hash the full payload bytes including the final row newline.

## Tenant object

Keys in order: `tenant_id`, `name`, `line_items`, `subtotal_microcents`, `credit_applied_microcents`, `commitment_discount_microcents`, `net_usage_microcents`, `shared_allocated_microcents`, `total_charge_microcents`

`line_items` is a JSON array, never null.

Ledger includes every active tenant even when usage is zero; `line_items` may be empty.

## Line item object

Keys in order: `service`, `units`, `list_cost_microcents`, `committed_units`, `committed_discount_microcents`, `on_demand_units`, `on_demand_cost_microcents`

## Summary object

Keys in order: `tenant_count`, `total_billable_microcents`, `pool_total_microcents`, `pool_unallocated_microcents`, `credit_applied_microcents`, `commitment_discount_microcents`

`total_billable_microcents` is the sum of tenant `total_charge_microcents`. Credit and commitment summary fields are sums across tenants. `pool_total_microcents` is the sum of period-matching pool totals.

## Serialization

`ledger.json` is UTF-8 pretty-printed JSON with two-space indentation, a space after each colon from `encoding/json`, and exactly one trailing newline. Only `/app/output/ledger.json` may be written under `/app/output`. Rebuild emits a Linux ELF at absolute `/app/bin/commitment-chargeback` (not a symlink; build artifacts must not remain under `carrydown_engine`).

## Editable sources

Repair work is limited to these four files under `/app/carrydown_engine`: `commitment.go`, `ratecard.go`, `intake.go`, and `main.go`. Leave every other `.go` file and `go.mod` in that directory byte-identical to the image baseline. Junk such as Makefile, JSON notes under the engine tree, and `cmd/` may be removed.
