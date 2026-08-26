# Selene survival game charter format

This file defines the complete input and output contract for the Selene turn-based survival game. All names and enum values are lowercase and case-sensitive. Every numeric value is a JSON integer, never a quoted number or a decimal. Object key order and whitespace do not matter after JSON parsing; array order does. Unless this file explicitly says that a field is ignored, extra or missing fields are invalid.

## Invocation and invalid input

At the beginning of every run, remove any existing `/workspace/colony_plan.json`. Decode exactly one JSON object from `/workspace/task_file/colony.json`; trailing non-whitespace data is invalid. Unknown fields, wrong JSON types, missing fields, duplicate object keys, and values outside the ranges below are invalid. On invalid input, exit nonzero and leave no `colony_plan.json`. The verifier's planning cases are valid; malformed-input behavior is checked separately from campaign semantics.

`case_id` is an opaque nonempty string used by operators. It has no effect and does not appear in the output.

The input fields are:

- `ruleset`: `"selene-1"` or `"selene-2"`.
- `population`: integer from 1 through 4.
- `regolith`: `"dry"` or `"volatile"`.
- `recycler`: `"off"`, `"oxygen"`, or `"water"`.
- `allow_emergency`: boolean.
- `capacities`: an object containing exactly `battery`, `oxygen`, `water`, `morale`, `hull`, `wear`, and `fatigue`. Each is an integer from 1 through 30.
- `initial`: an object containing exactly `battery`, `oxygen`, `water`, `morale`, `dust`, `hull`, `wear`, `insight`, and `fatigue`. `dust` and `insight` are integers from 0 through 30. Every other initial value is from 0 through its same-named capacity. Initial oxygen, water, morale, and hull must be positive.
- `targets`: an object containing exactly `insight`, `hull`, and `morale`. Each is an integer from 0 through 30; hull and morale targets may not exceed their capacities.
- `sols`: an array of zero through 10 sol objects. A sol contains exactly `id`, `sunlight`, and `hazard`. `id` is nonempty and unique in this array, `sunlight` is an integer from 0 through 12, and `hazard` is `"none"`, `"flare"`, `"impact"`, or `"quake"`. Array order is campaign order and supplies the one-based sol number.

## Campaign decisions

For every sol, choose exactly one ration policy and one operations directive. The ration policies are `full`, `conserve`, and `emergency`. `emergency` is not eligible when `allow_emergency` is false. The directives are `rest`, `sweep`, `mine`, `electrolyze`, `service`, `patch`, `brace`, and `research`.

All eligibility checks use the state at the precise phase stated below. A campaign is feasible only if every selected policy and directive is eligible, every required spend is available when it occurs, all capacity conditions hold, and the closing targets hold. An ineligible choice invalidates that complete campaign; it does not become a no-op and later phases do not rescue it.

Process each sol in this exact order: solar collection, directive, hazard, ration consumption, recycler, end-of-sol checks. Integers are exact; there is no rounding except the stated ceiling for emergency water.

### 1. Solar collection

Compute raw generation from the dust present at the start of the sol:

- `selene-1`: `max(0, sunlight - dust)`.
- `selene-2`: `max(0, sunlight - (dust + 1) / 2)`, where `/` is integer division. Thus the dust penalty is `ceil(dust/2)`.

Store as much raw generation as the battery capacity permits. Excess is spill. A `sweep` selected on this sol occurs later and therefore changes generation only on later sols.

### 2. Operations directive

First check the directive's conditions against the post-solar state. All listed spends happen before listed additions. A spend is eligible only when the full amount is available. Additions are capped at the corresponding capacity; the un-stored part is simply lost. Dust and wear reductions stop at zero. Directive fatigue is applied last as `max(0, old fatigue + delta)`. The ledger records actual stored additions and actual bounded state changes, not nominal amounts that spilled or went below zero.

The directives are:

| directive | condition | battery | water | other effect | fatigue delta |
|---|---|---:|---:|---|---:|
| `rest` | always | 0 | 0 | none | -2 |
| `sweep` | start-of-directive dust > 0 | -1 | 0 | remove 2 dust in `selene-1`, or 3 in `selene-2` | +1 |
| `mine` | resulting wear must not exceed wear capacity | -3 | add 5 in `dry`, or 7 in `volatile` | add 2 wear in `dry`, or 3 in `volatile` | +2 |
| `electrolyze` | required water is available | -3 | -2 | add 6 oxygen | +1 |
| `service` | start-of-directive wear > 0 | -2 | 0 | remove up to 3 wear | +1 |
| `patch` | start-of-directive hull is below hull capacity | -3 | 0 | add up to 3 hull | +2 |
| `brace` | always, including on `none` | -1 | 0 | protects only this sol's hazard | +1 |
| `research` | required water is available | -2 | -1 | add 3 insight; insight has no capacity | +1 |

The table's battery and water amounts are exact spends. For example, `mine` first spends 3 battery and then stores its water yield. Different directives do not combine on one sol.

### 3. Hazard

The selected directive is `brace` or it is not; no earlier brace persists. Apply exactly one row:

| hazard | with `brace` | without `brace` |
|---|---|---|
| `none` | no effect | no effect |
| `flare` | spend 1 oxygen | spend 3 oxygen and lose up to 2 morale |
| `impact` | lose up to 1 hull | lose up to 4 hull |
| `quake` | lose up to 1 hull | lose up to 2 hull and add 2 wear |

An oxygen spend must be fully available. Hull and morale losses are bounded at zero, but a zero hull or zero morale state is infeasible immediately. Quake wear is additive after any directive wear change; wear above capacity is infeasible immediately. Hazard effects do not short-circuit each other: without a brace, a flare applies both its oxygen and morale effects, and a quake applies both its hull and wear effects, in the table order.

### 4. Ration consumption

The policy applies to the entire population once per sol:

| policy | oxygen spend | water spend | morale change | fatigue added |
|---|---:|---:|---:|---:|
| `full` | `2 * population` | `2 * population` | +2 | 0 |
| `conserve` | `population` | `population` | -1 | +1 |
| `emergency` | `population` | `(population + 1) / 2` | -3 | +2 |

Here emergency water is `ceil(population/2)`. Oxygen is spent first, then water, then morale changes, then fatigue is added. Both spends must be fully available. Positive morale is capped at morale capacity; losses stop at zero. Zero morale is infeasible. Fatigue is not capped: a value above fatigue capacity is infeasible during the end-of-sol checks. Ration fatigue is additive to the directive's already-applied fatigue.

### 5. Recycler

Only after a successful ration phase, a non-off recycler attempts to return `population / 2` units using integer division. The return goes to the resource named by `recycler`, is capped by that resource's capacity, and may spill. The recycler never offsets a ration spend that was unaffordable before this phase. An `off` recycler returns zero and names `"off"` in the ledger.

### 6. End-of-sol checks and safety

Battery, oxygen, water, dust, hull, wear, insight, and fatigue must be nonnegative. Oxygen, water, morale, and hull must be strictly positive. Wear and fatigue must not exceed their capacities; all capped resources must not exceed capacity.

For a feasible sol, its safety value is `min(oxygen, water, morale, hull)` in the final state after recycling. Battery, wear, insight, and fatigue are deliberately not safety inputs. Campaign minimum safety is the minimum of all sol safety values.

After the last sol, final insight, hull, and morale must respectively be at least `targets.insight`, `targets.hull`, and `targets.morale`. Prior-state values remain part of the state and output even if no directive changes them.

For an empty `sols` array there are no decisions or ledger rows. Closing targets are checked against the initial state, and minimum safety is `min(initial oxygen, initial water, initial morale, initial hull)`. This is a valid feasible campaign when the targets hold; otherwise it is impossible.

## Selecting the one campaign

Compare only complete feasible campaigns. First prefer, in order:

1. larger campaign minimum safety;
2. larger final insight;
3. larger final morale;
4. larger final reserves, defined as final `battery + oxygen + water`;
5. smaller final wear;
6. fewer sols using `emergency`;
7. lexicographically smaller complete plan key by Unicode code-point order.

The plan key contains one token per sol, in campaign order. A token is `ration + ":" + directive`; tokens are joined with commas and no spaces. The seventh comparison is made only after constructing the complete campaign key. It never chooses between local directives or partial campaigns. The empty campaign key is the empty string.

## Output

Write exactly one JSON object with exactly these fields in this logical schema:

```text
status       string: "feasible" or "impossible"
ruleset      string copied from input
decisions    array
ledger       array
objective    object or null
```

If no complete feasible campaign exists, output exactly those five fields with `status: "impossible"`, empty `decisions` and `ledger` arrays, and `objective: null`. Rejected partial campaigns never appear and never contribute to output counts or totals.

For the selected feasible campaign, `status` is `"feasible"`. `decisions` has one row per input sol in the same order. Each row has exactly:

```text
sol            integer, one-based
id             string copied from that sol
ration         selected policy
directive      selected directive
hazard_result  one of "none", "braced_flare", "open_flare",
               "braced_impact", "open_impact", "braced_quake", "open_quake"
```

For hazard `none`, `hazard_result` is always `"none"`, even when the directive is `brace`. For another hazard, use its `braced_` form exactly when the directive is `brace`, otherwise its `open_` form.

`ledger` also has one row per input sol in the same order. Each row contains exactly `sol`, `start`, `solar`, `directive`, `hazard`, `ration`, `recycle`, and `end`. `sol` is one-based. `start` is the previous sol's `end`, or the input `initial` state on sol 1. Both `start` and `end` contain exactly these integer fields:

```text
battery oxygen water morale dust hull wear insight fatigue
```

The flow objects contain actual movements for the selected feasible campaign and exactly these fields:

```text
solar:     raw, added, spill
directive: battery_spent, oxygen_added, water_spent, water_added,
           hull_added, dust_removed, wear_delta, insight_added, fatigue_delta
hazard:    oxygen_spent, hull_lost, morale_lost, wear_added
ration:    oxygen_spent, water_spent, morale_delta, fatigue_added
recycle:   resource, added, spill
```

Every flow value except `recycle.resource` is an integer. Spends, losses, removals, additions, and spill are nonnegative. `wear_delta`, `fatigue_delta`, and `morale_delta` are signed actual changes and may be negative. `recycle.resource` is exactly the input recycler enum. Flow objects describe their own phase only. For example, quake wear belongs in `hazard.wear_added`, not `directive.wear_delta`, and recycler additions do not reduce `ration.water_spent`.

`objective` contains exactly:

```text
minimum_safety  integer
final_insight   integer
final_morale    integer
final_reserves  integer
final_wear      integer
emergency_sols  integer
plan_key        string
```

These are the selected complete campaign's seven comparison components in display form. `final_reserves` includes only battery, oxygen, and water. `emergency_sols` counts selected decision rows whose ration is `emergency`; it does not count considered or rejected campaigns.
