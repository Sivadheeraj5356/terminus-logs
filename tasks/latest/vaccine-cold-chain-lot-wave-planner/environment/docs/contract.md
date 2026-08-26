# immunoflow contract

## Shared FEFO lot pool
Regions are visited in ascending `region_id` order. Lots matching `storage_temp` are drawn from one shared remaining-dose pool. Earlier regions permanently deplete pool stock for later regions. Within a draw, lots are consumed in ascending `expiry_day`, breaking ties by ascending `lot_id`.

## Vial remainder ledger
`/app/var/immunoflow_vialremainder.json` stores per-lot remainder doses. At pool construction, each lot's available doses equal `lot.doses - remainder[lot_id]` (floored at zero). After each draw, remainder for a touched lot becomes `(prior_remainder + doses_drawn) % vial_size` from config.

## Dose-2 wave
`dose2_wave = dose1_wave + ceil(min_gap_days / 7)` using integer ceiling via `(min_gap_days + 6) // 7`.

## Gap weeks helper
`gap_weeks = ceil(min_gap_days / 7)` using the same integer ceiling. Infection projection multiplies uncovered demand by this value.

## Equity reconciliation
Each region row in `/app/data/immunolab/regions.json` includes `demand_dose1` and `equity_floor`. `region_delivered` counts only doses actually assigned to each region. Reserve doses from config are not deliverable and must not be added to regional totals. Allocation `region_coverage.delivered` mirrors those assigned doses (not reserve-inflated figures).

## Shipment legs CSV
`/app/output/shipment_legs.csv` is UTF-8 CSV. The header row is exactly `leg_id,region_id,lot_id,depart_day,arrive_day,temp_band`. Each lot assignment produces one data row. `leg_id`, `depart_day`, and `arrive_day` are copied from the route whose `region_id` matches the assignment. `temp_band` is the assigned lot's storage band.

## Cold-chain pallets
`coldchain_audit.pallets` is a JSON object keyed by pallet key; each value is an array of `lot_id` strings. Each key must contain lots sharing one `temp_band`; valid packing has `ok` true and mixed-band keys have `ok` false. When mixed bands would share a base `pallet_id`, split into keys formed as `{pallet_id}-{temp_band}` so every key remains single-band. Deck packing for bind-lanes is computed by the Rust `pkmerge` tool at `/app/bin/pkmerge` (sources under `/app/environment/pkmerge`).

`coldchain_audit.spoilage_rows` is a JSON array of spoilage records; the wave-3 canonical pipeline emits an empty array when no spoilage events occur. `coldchain_audit.lane_digest_hex` is lowercase hex SHA-256 over the Go `%v` string form of the `pallets` map produced by bind-lanes.

## Inspect projection
`immunoflow inspect --generation G` exits 0. When `G` equals the scopebook generation stored with the cache, stdout is the cached allocation plan JSON. When `G` does not match, stdout is `{"wave":0,"lot_assignments":[]}` with `wave` 0 and empty `lot_assignments` — not an error and not a stale cached plan.

## Dose schedule JSON
`/app/data/immunolab/clinics.json` lists clinic rows keyed by region with `min_gap_days`. `dose_schedule.json` includes `schedule` rows with `clinic_id`, `dose1_wave`, `dose2_wave`, and `min_gap_days`.

## Scopebook lane hours
`total_lane_hours` accumulates lane hours from every plan-wave and spoilage-replan invocation.

## Customs accrual
On each plan-wave, `immunoflow_customs.json` `total_delay_days` increases by the assignment-scoped route-delay `delta`: the sum of `customs_delay_days` only for routes whose `region_id` appears in at least one lot assignment. Unserved regions contribute nothing.

## Plan digest
`plan_digest_hex` is lowercase hex SHA-256 over `wave|sorted(region:lot:doses tuples)`.

## Infection projection
`infection_projection.json` rows include `region_id` and `projected_cases`. For each region, `projected_cases = max(need - delivered, 0) * gap_weeks` where `gap_weeks` comes from that region's clinic `min_gap_days` and `need`/`delivered` come from allocation `region_coverage`.

## Feasibility report
`feasibility_report.json` includes `feasible`, which matches `equity_met` from the allocation plan for the same wave.

## Pipeline commands
Wave-3 verification reruns `immunoflow bench reset`, then `plan-wave --lab /app/data/immunolab --wave 3 --out /app/output/allocation_plan.json`, `bind-lanes`, `schedule-doses`, `reconcile-equity`, and `project-infections --lab /app/data/immunolab --plan /app/output/allocation_plan.json`. Spoilage and customs checks invoke additional `plan-wave` and `spoilage-replan` runs with the same `--lab`, `--wave`, and `--out` flags.

## Verifier companion tooling
Offline verifier helpers under `/tests/immunoflow_ref.py` may shell out to `sha256sum` for digest checks.
