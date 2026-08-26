# Thermal cycle report contract

The command accepts `--config` and `--out`, each exactly once. Both values must be absolute paths. A valid run replaces the output directory with six UTF-8 files named `field.csv`, `events.csv`, `summary.json`, `trace.csv`, `material_profile.csv`, and `stability.csv`. Configuration and argument errors must return a nonzero status before the output path is touched. A later failure may remove its own staging data but must leave an existing output directory unchanged.

## Configuration

The JSON root is an object with these fields. Every numeric config value must be a JavaScript safe integer, from -9,007,199,254,740,991 through 9,007,199,254,740,991, before any narrower bound below is applied. All calculations and reported integer values must be exact. Intermediate products, sums, and aggregate totals can exceed this safe-integer range even though each config value is safe, so the implementation must use integer arithmetic that does not lose precision. Apply each stated floor only after the exact numerator has been formed.

- `scenario` is a nonempty string.
- `width` and `height` are integers from 5 through 80. `steps` is an integer from 1 through 200.
- `block_width` and `block_height` are positive integers. `material_offset` is a nonnegative integer.
- `base_temperature_milli_c`, `temperature_floor_milli_c`, `temperature_ceiling_milli_c`, and `activation_temperature_milli_c` are integers. The floor is less than the ceiling and activation is within that closed range.
- `base_cure_ppm` is from 0 through 1,000,000. `full_cure_ppm` and `stress_alert_ppm` are from 1 through 1,000,000.
- `checkpoint_steps` is a strictly increasing integer list whose first value is 0 and last value is `steps`.
- `materials` contains two through five objects. Each has nonnegative integer `retain`, `horizontal`, `vertical`, `diagonal`, `heater_gain`, `stress_gain`, `cure_stress_gain`, and `stress_relief_ppm` values, integer `stress_retain_ppm` from 0 through 1,000,000, plus positive integer `cure_rate_ppm` and `cool_rate_ppm` values. The sum `retain + 2 * horizontal + 2 * vertical + 4 * diagonal` must be positive.
- `boundaries` has `left`, `right`, `top`, and `bottom`. Each has integer `temperature_milli_c` within the configured temperature range and integer `cure_ppm` from 0 through 1,000,000.
- `hotspots` is a list of objects with integer `x`, `y`, `peak_milli_c`, and `decay_per_cell_milli_c`. Coordinates must be in the grid and the last two values must be nonnegative.
- `heater_pulses` is a list of objects with integer `start_step`, `end_step`, `x`, `y`, `strength_milli_c`, and `decay_per_cell_milli_c`. The step interval is inclusive and must fit from 1 through `steps`. Coordinates must be in the grid and the last two values must be nonnegative.
- `relief_windows` is a list of objects with integer `start_step`, `end_step`, `x`, `y`, `radius`, `relief_ppm`, and `falloff_ppm_per_cell`. The step interval is inclusive and must fit from 1 through `steps`. Coordinates must be in the grid and the last three values must be nonnegative.
- `sensor_points` is a list of one through eight objects. Each object has a unique nonempty string `name` containing only ASCII letters, digits, `_`, or `-`, plus integer `x` and `y` coordinates inside the grid.

Unknown fields may be ignored. Invalid JSON or any violation above makes the whole configuration invalid.

## Grid rules

Coordinates start at zero and fields are stored by row as `[y][x]`. Boundary precedence is left, right, top, then bottom. A boundary cell always uses the configured temperature and cure values from the first matching side in that order.

For an interior cell, initial temperature is `base_temperature_milli_c` plus every hotspot contribution. A hotspot contributes `max(0, peak_milli_c - decay_per_cell_milli_c * (abs(x - hotspot.x) + abs(y - hotspot.y)))`. Clamp the result to the configured temperature range. Initial interior cure is `base_cure_ppm`.

The material index at any coordinate is:

`(floor(x / block_width) + 2 * floor(y / block_height) + material_offset) mod materials.length`

## Step update

All temperature cells in a step use the complete temperature and cure fields from the preceding step. For an interior cell, let `R`, `H`, `V`, and `D` be its material's retain, horizontal, vertical, and diagonal values. Compute:

`mixed = floor((R * center + H * (west + east) + V * (north + south) + D * (northwest + northeast + southwest + southeast)) / (R + 2 * H + 2 * V + 4 * D))`

Every pulse active at the current step contributes `max(0, strength_milli_c - decay_per_cell_milli_c * ManhattanDistance)` to that cell. Also add `floor((old_cure_ppm - base_cure_ppm) * heater_gain / 1,000,000)`. Clamp the sum of `mixed`, all active pulse contributions, and the cure term to the configured temperature range. Boundary cells instead take their fixed configured temperature.

Cure is updated after the entire next temperature field is available. For each interior cell, use its next temperature and preceding cure. At or above the activation temperature, add `cure_rate_ppm + floor((next_temperature_milli_c - activation_temperature_milli_c) / 2500)`. Below activation, subtract `cool_rate_ppm`. Clamp cure to 0 through 1,000,000. Boundary cells keep their fixed configured cure.

An event occurs only on the first step where an interior cell moves from below `full_cure_ppm` to at or above it. Starting above the threshold is not an event. A later drop and recrossing must not create another event. Events are ordered by step, then y, then x.

Stress is updated after the next cure field is available. Stress starts at 0 for every cell. Boundary stress is always 0. For an interior cell, use the preceding stress, preceding temperature and cure, and the just-computed next temperature and cure:

`generated_stress = floor((abs(next_temperature_milli_c - old_temperature_milli_c) * stress_gain + max(0, next_cure_ppm - old_cure_ppm) * cure_stress_gain) / 1000)`

`retained_stress = floor(old_stress_ppm * stress_retain_ppm / 1,000,000)`

Each active relief window contributes only when the Manhattan distance from its `(x, y)` is at most `radius`. Its contribution is `max(0, relief_ppm - falloff_ppm_per_cell * distance)`. Subtract the material's `stress_relief_ppm` plus all active window contributions from `retained_stress + generated_stress`, then clamp to 0 through 1,000,000.

A stress event occurs only on the first step where an interior cell moves from below `stress_alert_ppm` to at or above it. Starting at or above the threshold is not an event. A later drop and recrossing must not create another event. Stress events are ordered by step, then y, then x.

Checkpoint step 0 describes the initial fields. Each configured checkpoint records `total_temperature_milli_c`, `total_cure_ppm`, `hot_cell_count`, `full_cure_cell_count`, `peak_stress_ppm`, and `stressed_cell_count`. A hot cell is at or above the activation temperature. A full-cure cell is at or above `full_cure_ppm`. A stressed cell is at or above `stress_alert_ppm`. The temperature, cure, and stress fields at every configured checkpoint must also be preserved for the sensor trace and stability output.

## Output

`field.csv` has the header `x,y,material,temperature_milli_c,cure_ppm` and one row per final cell in row-major order: iterate y from 0 through height - 1, and within each y iterate x from 0 through width - 1.

`events.csv` has the header `step,x,y,material,temperature_milli_c,cure_ppm` and one row per event in the event order above.

`summary.json` is pretty-printed with a final newline. Its keys, in order, are `scenario`, `width`, `height`, `steps`, `min_temperature_milli_c`, `max_temperature_milli_c`, `mean_temperature_milli_c`, `hot_cell_count`, `full_cure_cell_count`, `peak_stress_ppm`, `stressed_cell_count`, `total_temperature_milli_c`, `total_cure_ppm`, `center_row_checksum`, `center_column_checksum`, `event_count`, `first_full_cure_step`, `stress_event_count`, `first_stress_alert_step`, and `checkpoint_totals`. Mean temperature rounds to the nearest integer with half values rounding up. The center row is `floor(height / 2)` and its checksum is the sum of `(x + 1) * temperature[center_y][x]`. The center column is `floor(width / 2)` and its checksum is the sum of `(y + 1) * temperature[y][center_x]`. `first_full_cure_step` is the first cure event step or null. `first_stress_alert_step` is the first stress event step or null. Checkpoint keys are decimal step strings in ascending numeric order.

`trace.csv` has the header `checkpoint,name,x,y,material,temperature_milli_c,cure_ppm,local_gradient_milli_c,temperature_delta_from_previous_checkpoint_milli_c`. For every configured checkpoint in ascending numeric order, write one row for each configured sensor point in input order. The material is the material index at that coordinate. `local_gradient_milli_c` is the largest absolute temperature difference between the sensor cell and any existing cardinal neighbor in that checkpoint field. Missing neighbors outside the grid are ignored. If no cardinal neighbor exists, the gradient is 0. The temperature delta is the sensor temperature at the current checkpoint minus the same sensor's temperature at the previous configured checkpoint. For checkpoint 0, the delta is 0.

`material_profile.csv` has the header `material,cell_count,mean_temperature_milli_c,total_cure_ppm,peak_stress_ppm,stress_event_count,first_full_cure_step` and one row for every material index from 0 through `materials.length - 1`. `cell_count`, `mean_temperature_milli_c`, `total_cure_ppm`, and `peak_stress_ppm` are computed from the final fields for cells with that material index. Mean temperature rounds to the nearest integer with half values rounding up. If a material has no final cells, use `0`, blank mean temperature, `0` total cure, `0` peak stress, and `0` stress events. `stress_event_count` is the number of first stress-alert events for that material. `first_full_cure_step` is the earliest cure event step for that material, or blank if that material never has a full-cure event.

`stability.csv` has the header `checkpoint,material,peak_stress_ppm,mean_stress_ppm,stressed_cell_count,new_stress_events` and one row for every configured checkpoint in ascending numeric order, then every material index in ascending numeric order. Stress statistics are computed from the checkpoint stress field for cells with that material index. `mean_stress_ppm` rounds half up, and is blank when the material has no cells. `new_stress_events` counts first stress-alert events for that material with step greater than the previous configured checkpoint and less than or equal to the current checkpoint. For checkpoint 0, it is always 0.
