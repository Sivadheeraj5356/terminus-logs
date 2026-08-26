# Graph layout

Fixtures live under `/app/environment/fixtures/`.

## linear_smoke

Chain: `step_a -> step_b -> step_c`. Each step produces one partition consumed by the next. All jobs submit at tick 0.

## diamond_mesh

Diamond: `root` fans out to `left` and `right`, which converge at `merge`. Partitions 0–3 are used. All jobs submit at tick 0.

## gradual_mesh

Same dependency shape as `diamond_mesh` with staggered submit ticks: `root` at 0, `left` at 2, `right` at 4, `merge` at 6.

## fan_in

`root` fans out to four arms (`arm_a`–`arm_d`) that converge at `bundle`. Partitions 0–5 are used. All jobs submit at tick 0.

Each job row in fixtures includes `duration`, `deps`, `input_parts`, `output_part`, and `submit_tick`.
