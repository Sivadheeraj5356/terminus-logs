# Sterile-dose cohort model contract

The simulator reads six required CSV files from the input directory. CSV records may use LF or CRLF endings. A physical record containing only spaces or tabs is ignored for parsing, but every raw byte remains part of `input_digest`. Headers and row widths are exact; fields are not trimmed. All integer fields are unsigned ASCII decimal values. `grams_per_unit`, `units`, `max_lots`, `vial_grams`, and `max_open_cycles` are positive; other integers may be zero. In particular, `prime_grams` may be zero. Valid inputs keep every product, intermediate value, and sum within signed 64-bit range.

Identifier columns are case-sensitive ASCII tokens of 1 through 64 characters matching `[A-Za-z0-9._~-]+`. This rule applies to every `lot_id`, `material_id`, `product_id`, `order_id`, `family`, `substitute_family`, and `assay_group` field, including identifiers on rows that are later ignored or deduplicated. Preserve their exact CSV text, emit identifier fields as JSON strings, and compare identifier tie-breakers using lexicographic string order. Enumerated strings are defined below.

## Valid workload limits

After whitespace-only physical records are ignored, each CSV file may contain at most 128 data rows, excluding its header. After deduplication there may be at most 12 surviving lots, 16 surviving formulas, and 8 surviving orders. Every surviving formula must have `max_lots <= 3`. For every surviving order whose product has a formula, `units * grams_per_unit` must be at most 96.

An order may have at most 4096 physically and robust-potency-feasible local allocations before budget filtering. The cohort search size is the product, over eligible orders, of `1 +` that order's number of budget-compliant allocations; it must be at most 2000000. Inputs exceeding any workload limit are invalid.

## Input tables

`lots.csv`

`lot_id,material_id,family,potency_mg_per_g,uncertainty_mg_per_g,grams,prime_grams,expires_day,open_stability_days,status,cost_cents_per_g`

`status` is `active` or `hold`. For repeated `lot_id` values, retain the row with highest potency, then lowest uncertainty, then lowest expiry day, then smallest material ID; an exact tie retains the earlier row.

`assays.csv`

`lot_id,assay_group,assay_day,valid_through_day,decay_mg_per_g_per_day,uncertainty_growth_mg_per_g_per_day`

The last row for a repeated `lot_id` wins. Every surviving lot must have an assay row and `valid_through_day >= assay_day`. Rows for unknown lot IDs are ignored after validation.

`packaging.csv`

`lot_id,vial_grams,max_open_cycles,open_decay_mg_per_g_per_day,open_uncertainty_growth_mg_per_g_per_day`

The last row for a repeated `lot_id` wins. Every surviving lot must have a packaging row. Rows for unknown lot IDs are ignored after validation. The two open-vial rates are nonnegative integers.

`formulas.csv`

`product_id,required_material_id,grams_per_unit,min_robust_potency_mg_per_unit,uncertainty_budget,max_lots,mix_loss_mg_per_extra_lot,substitute_family,substitution_penalty_cents_per_g`

The last row for a repeated `product_id` wins. `substitute_family` equal to `-` disables substitution. `uncertainty_budget` counts assay groups, not lots.

`orders.csv`

`order_id,product_id,units,requested_day,priority,max_cost_cents`

`priority` is `urgent`, `normal`, or `standby`, with ranks 0, 1, and 2. For repeated `order_id` values, retain lowest rank, then largest units, then lowest requested day, then smallest product ID; an exact tie retains the earlier row.

`events.csv`

`lot_id,kind,day,grams`

`kind` is `loss`, `restock`, `hold`, or `release`. Event `day` is an unsigned integer. After lot deduplication and metadata validation, events for each surviving lot are ordered by `day`, then original file order for ties. Unknown lot IDs are ignored after their identifier, kind, day, and grams have been validated. Loss floors currently available unopened grams at zero, restock adds unopened grams, and hold/release update status. For candidate allocation eligibility, apply all events with `day <= requested_day`; same-day events apply before same-day order eligibility. The `grams` value on hold/release rows is parsed but does not otherwise change inventory.

## Time-dependent assay model

A lot is assay-eligible for an order only when `assay_day <= requested_day <= valid_through_day`. Let `age = requested_day - assay_day`.

Effective potency per gram is:

`max(0, potency_mg_per_g - age * decay_mg_per_g_per_day)`

Effective uncertainty per gram is:

`uncertainty_mg_per_g + age * uncertainty_growth_mg_per_g_per_day`

Both values are integers.

## Order allocations

An order with no surviving formula is rejected `UNKNOWN_PRODUCT`. Otherwise candidate lots are active after applying events through the requested day, have positive unopened grams after those events, unexpired on the requested day, assay-eligible, and either use the required material or a different material in the allowed substitute family.

For an allocation, let `g_i` be dispensed grams from lot `i`. It must satisfy:

- `sum(g_i) = units * grams_per_unit`;
- at most `max_lots` values of `g_i` are positive;
- each used lot can satisfy the order alone as one opening episode using unopened grams available after events through that order day: `ceil((g_i + prime_grams) / vial_grams) * vial_grams <= available grams`;
- nominal potency is the sum of `g_i * effective_potency_per_gram` at the order day;
- each used lot contributes `g_i * effective_uncertainty_per_gram` to its `assay_group`;
- group contributions are summed first; uncertainty deduction is the sum of the largest `uncertainty_budget` group totals, or all group totals when fewer groups are used;
- mixing loss is `mix_loss_mg_per_extra_lot * max(0, used_lot_count - 1)`;
- robust potency is `max(0, nominal potency - uncertainty deduction - mixing loss)` and must reach `units * min_robust_potency_mg_per_unit`.

Dispensed cost is lot cost plus substitute penalty for different-material family substitutes. It is based only on dispensed grams; priming and vial waste do not count against the order budget. Substitute grams count only substitutes. Expiry risk is `sum(g_i * (expires_day - requested_day))`. Robust margin is robust potency minus required robust potency. Local allocation enumeration evaluates every used lot as a fresh opening on the order day, so its open age is zero. The allocation key lists positive draws by lot ID as `lot_id:grams`, joined with commas.

If no allocation satisfies the physical and robust-potency rules, reject `NO_MATERIAL`. If such allocations exist but all exceed `max_cost_cents`, reject `OVER_BUDGET`. Remaining orders are eligible for the cohort plan.

## Opening episodes and discrete vial consumption

For every lot in a candidate cohort plan, collect all selected uses as `(requested_day, dispensed_grams)` and combine uses on the same day. Sort days ascending. Partition them greedily into minimum opening episodes: an episode starts at the first unused day and contains every following day no later than `episode_start + open_stability_days`; the next unused day starts another episode.

Each episode incurs one `prime_grams` charge. If an episode dispenses `d` grams, its consumed inventory is:

`ceil((d + prime_grams) / vial_grams) * vial_grams`

Its vial waste is consumed inventory minus `d` minus `prime_grams`. For a lot, the number of episodes must not exceed `max_open_cycles`. Each episode consumes unopened whole-vial inventory on its episode start day, after any events on that same day have been applied. Replay each lot chronologically from its deduplicated starting grams and status, applying events by day and file-order tie-break, then same-day episode consumption. The plan is infeasible if an episode consumption would exceed unopened grams available at that moment. `opened_vial_count` is total consumed inventory divided by `vial_grams`.

For a selected use on day `d` in an episode that starts on day `s`, `open_age = d - s`. Recompute that use with:

`post_open_potency_per_gram = max(0, effective_potency_per_gram - open_age * open_decay_mg_per_g_per_day)`

`post_open_uncertainty_per_gram = effective_uncertainty_per_gram + open_age * open_uncertainty_growth_mg_per_g_per_day`

The order's final nominal potency and assay-group uncertainty contributions use these post-open values. `open_decay_loss_mg` is the sum of dispensed grams times the difference between effective and post-open potency. `open_uncertainty_growth_mg` is the sum of dispensed grams times the difference between post-open and effective uncertainty. Recompute uncertainty deduction, robust potency, and robust margin from these final values. A cohort plan is infeasible if any selected order then falls below its robust potency target, even though that order was locally feasible as a fresh opening.

## Cohort plan

Choose a subset of eligible orders and one budget-compliant allocation for every selected order. A plan is feasible only when every lot satisfies the opening-episode and inventory rules above and every selected order remains robust-potency feasible after open-age degradation is applied.

Compare complete plans by, in order: most urgent orders, most urgent units, most normal orders, most normal units, most standby orders, most standby units, fewest distinct opened lots, fewest total prime cycles, least total vial waste, least total dispensed cost, least total uncertainty deduction, least substitute grams, least expiry risk, greatest total robust margin, then lexicographically smallest global allocation key. The global key lists selected orders by order ID as `order_id=allocation_key`, joined with semicolons. Eligible orders omitted from the winning plan are rejected `DEFERRED_CAPACITY`.

## Output report

Top-level keys are exactly `schema`, `input_digest`, `orders`, `rejections`, `materials`, `cohort_audit`, and `summary`. `schema` is `amberglass.v6`. Every successful output file ends with one trailing LF newline byte after the JSON document.

`input_digest` is lowercase SHA-256 over `lots.csv`, `assays.csv`, `packaging.csv`, `formulas.csv`, `orders.csv`, and `events.csv` in that order. For each file, hash ASCII filename, NUL, ASCII decimal raw-byte length, NUL, exact raw bytes, NUL.

`orders` are sorted by priority rank, requested day, then order ID. Each object has exactly:

`order_id`, `product_id`, `status`, `grams`, `nominal_potency_mg`, `open_decay_loss_mg`, `uncertainty_deduction_mg`, `open_uncertainty_growth_mg`, `mix_loss_mg`, `robust_potency_mg`, `robust_margin_mg`, `cost_cents`, `substitute_grams`, `lots`

`status` is `FILLED`. Numeric fields are JSON integers. `lots` is sorted by lot ID and each object has exactly `lot_id`, `material_id`, and integer `grams`.

`rejections` are sorted by order ID. Each has exactly `order_id` and `reason`, where reason is `UNKNOWN_PRODUCT`, `NO_MATERIAL`, `OVER_BUDGET`, or `DEFERRED_CAPACITY`.

`materials` are sorted by lot ID. Each has exactly:

`lot_id`, `remaining_grams`, `prime_cycles`, `primed_grams`, `vial_waste_grams`, `opened_vial_count`, `opened`, `first_use_day`, `last_use_day`, `status`

Use JSON null for both day fields when unopened; otherwise both are integers. `remaining_grams` is the final unopened grams after all events and all consumed whole-vial inventory, including dispensed grams, priming, and waste. `status` is the final lot status after all events.

`cohort_audit` contains urgent, normal, and standby in that order. Each object has exactly:

`priority`, `eligible_order_count`, `filled_order_count`, `filled_units`, `opened_lot_count`, `prime_cycle_count`, `vial_waste_grams`, `opened_vial_count`, `nominal_potency_mg`, `open_decay_loss_mg`, `uncertainty_deduction_mg`, `open_uncertainty_growth_mg`, `mix_loss_mg`, `robust_potency_mg`, `robust_margin_mg`, `total_cost_cents`, `substitute_grams`, `expiry_risk`, `allocation_key`

Counts and potency/cost totals reflect eligible or selected orders of that priority. Recompute opened-lot, prime-cycle, vial-waste, and opened-vial values using only selected uses of that priority. Its key uses the global-key format restricted to that priority.

`summary` has exactly integer `filled_count`, `rejected_count`, `total_cost_cents`, `total_dispensed_grams`, `total_prime_cycles`, `total_prime_grams`, `total_vial_waste_grams`, `total_opened_vials`, `opened_lot_count`, `total_open_decay_loss_mg`, `total_open_uncertainty_growth_mg`, `robust_margin_mg`, and lowercase SHA-256 `digest`.

The summary digest input ends with a newline and contains these rows in output order:

`I|input_digest`

`A|priority|eligible_order_count|filled_order_count|filled_units|opened_lot_count|prime_cycle_count|vial_waste_grams|opened_vial_count|nominal_potency_mg|open_decay_loss_mg|uncertainty_deduction_mg|open_uncertainty_growth_mg|mix_loss_mg|robust_potency_mg|robust_margin_mg|total_cost_cents|substitute_grams|expiry_risk|allocation_key`

`F|order_id|cost_cents|nominal_potency_mg|open_decay_loss_mg|uncertainty_deduction_mg|open_uncertainty_growth_mg|mix_loss_mg|robust_potency_mg|robust_margin_mg|substitute_grams|allocation_key`

`R|order_id|reason`

`M|lot_id|remaining_grams|prime_cycles|primed_grams|vial_waste_grams|opened_vial_count|opened|first_use_day|last_use_day|status`

Material booleans are lowercase `true` or `false`; null day values are `-`.

## Failure behavior

Wrong argument count, missing or unreadable directories/files, malformed CSV, invalid identifier syntax, invalid integer syntax or range, zero in a positive-only field, a workload-limit violation, unknown enum values, missing assay or packaging metadata for a surviving lot, or an assay validity interval with end before start are errors. Exit non-zero and remove the requested output whenever a second positional argument is available.
