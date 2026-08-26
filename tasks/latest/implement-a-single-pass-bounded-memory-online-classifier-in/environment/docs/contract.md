# Household Power Gap-Aware Submeter EWMA Contract

## Inputs

Each run receives one data directory with five CSV files. All CSV files have headers; parse by header name.

`readings.csv` has one row per event:

- `event_id`: contiguous integer event order starting at 0
- `local_date`, `local_time`: civil timestamp strings
- `daypart_id`: state bucket name
- `global_active_power_kw`, `global_reactive_power_kvar`, `voltage_v`, `global_intensity_a`, `sub_metering_1_wh`, `sub_metering_2_wh`: visible measurements, blank on missing rows
- `missing_flag`: `1` for a missing measurement event, otherwise `0`

`prediction_requests.csv` has `request_id,event_id,threshold_share`. Requests appear only for observed events. A stream may contain multiple requests for the same event and threshold.

`label_arrivals.csv` has `arrival_event_id,source_event_id,sub_metering_3_wh`. A label row releases the withheld target for a prior source event. The released target applies to every pending request whose `event_id` equals that source event. Some labels arrive at the same event as the request; some arrive after the final event and are processed as a terminal flush with no new predictions.

`learner_config.csv` has key/value rows for:

- `alpha`
- `prior_strength`
- `page_hinkley_delta`
- `page_hinkley_lambda`
- `reset_cooldown`
- `gap_decay`
- `max_label_delay`
- `probability_epsilon`
- `dayparts`, a `|` separated ordered list

`score_windows.csv` has `window_id,start_event_id,end_event_id`, inclusive.

## Event Order

Process events in increasing `event_id`.

For a missing row, first multiply every daypart's EWMA positive count and effective weight by `gap_decay`. A missing row is not a negative label and creates no prediction.

For an observed row, answer all requests at that `event_id` before processing labels whose `arrival_event_id` is the same event. For a request in daypart `d`, emit

`p = (pos[d] + 0.5 * prior_strength) / (weight[d] + prior_strength)`.

Store the request id, source event, daypart, visible active power, threshold, and probability until its label arrives. You may keep only pending delayed requests, daypart state, score accumulators, and output rows; do not cache the full stream for learning.

After prediction output for the event, process all labels whose `arrival_event_id` equals that event, sorted by increasing `source_event_id`. After the final reading event, process remaining labels by increasing `arrival_event_id` and then `source_event_id` as terminal flush records.

## Label Update

For each pending request released by a label:

1. Compute `known_wh = global_active_power_kw * 1000 / 60` from the visible source row.
2. Compute `y = 1` when `sub_metering_3_wh / known_wh >= threshold_share`, else `0`.
3. Score the stored prediction with Brier loss `(p - y)^2` and log loss `-(y*ln(p) + (1-y)*ln(1-p))`, clamping `p` into `[probability_epsilon, 1 - probability_epsilon]` only for log loss.
4. Update the source daypart EWMA:
   - `pos = (1 - alpha) * pos + alpha * y`
   - `weight = (1 - alpha) * weight + alpha`
5. Update Page-Hinkley on residual `r = y - p`:
   - `seen += 1`
   - `resid_mean += (r - resid_mean) / seen`
   - `ph = max(0, ph + r - resid_mean - page_hinkley_delta)`
   - if `cooldown > 0`, decrement it by 1
   - if `ph > page_hinkley_lambda` and `cooldown == 0`, append a reset record with the current arrival event and daypart, reset that daypart's `pos`, `weight`, `ph`, `resid_mean`, and `seen` to zero, and set `cooldown = reset_cooldown`

## Output JSON

Print exactly one JSON object:

- `n_events`: number of reading events
- `n_predictions`: number of emitted predictions
- `n_labels`: number of scored pending requests
- `n_missing_events`: number of missing reading events
- `predictions`: ordered array of `{request_id,event_id,probability}`
- `resets`: ordered array of `{event_id,daypart_id}`
- `windows`: ordered array of `{window_id,n_scored,brier,log_loss}`. `brier` and `log_loss` are averages, or `null` for empty windows.
- `final_state`: object with `gap_events`, `labels_applied`, and ordered `dayparts`. Each daypart row has `daypart_id,pos,weight,ph,resid_mean,seen,cooldown`.

Floating point values must be accurate within `1e-9`.
