# Text log columns

Partial text excerpts under `environment/fixtures/log_txt/` mirror a subset of runtime columns.

| Column | Meaning |
|--------|---------|
| `event_total` | Accepted event rows for the side |
| `combo_remain` | Remaining activation depth after sweep |
| `col_a` | Local interim checksum column (`col_a` means the local side column; may match tally while matrix diverges) |
| `col_b` | Remote interim checksum column (`col_b` means the remote side column) |
| `entropy_band` | Observed band midpoint from local-only math |

Authoritative bytes for graded replay live in `environment/fixtures/ev_bins/*.evb`. When log excerpts disagree with ev bin payloads, trust the ev bin bytes and rebuild through the public matrix command.
