# Maintenance windows

JSON object with `windows` array. Each window:

- `window_id`
- `vessel_id`
- `start_unix` / `end_unix`
- `kind` (string)

A vessel is in maintenance at epoch `E` when there exists a window for that vessel with:

`start_unix <= E < end_unix`

(half-open interval). Exact equality with `end_unix` is not a maintenance block.
