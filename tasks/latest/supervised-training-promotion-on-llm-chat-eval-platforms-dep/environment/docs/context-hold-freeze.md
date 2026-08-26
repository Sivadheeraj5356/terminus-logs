# Context hold freeze

`context_hold_freeze.json` sealed during `score-contam-window`:

| Field | Meaning |
|-------|---------|
| `corpus_stamp` | Live digest at seal time |
| `cutoff` / `emitted_at` | Clocks |
| `row_count` | Contam rows sealed |
| `pin_digest` | SHA-256 over newline-joined compact sorted JSON of each contam row |
| `report` | Full bulletin payload |

Emit must write `report` from this freeze after verifying digests.
