# Booking Slot Merge

`slot-merge` coalesces room and resource booking intervals stored as JSONL in
`*.slot` files. The verifier rebuilds `/app/target/release/slot-merge` from
your source after you edit it.

Output from the tool does not always match the rules below.

Each non-empty line is one JSON object with `resource` (bookable resource id),
`start_ms` and `end_ms` (unsigned millisecond timestamps where `end_ms` is
inclusive), `holder` (booking owner string), `slot_id` (unique record id), and
optional `epoch` (unsigned fencing token, default `0`). Example:
`{"resource": "room-12", "start_ms": 1000, "end_ms": 2000, "holder": "team-a", "slot_id": 4, "epoch": 2}`.
Files are read in ascending (lexicographic) filename order. Resource ids are
compared case-insensitively when grouping slots.

Only slots at a resource's **maximum epoch** participate in `merge`, `gaps`, and
`report`. Lower-epoch rows are fenced out of those commands but still count in
`stats` and participate in `check`.

## `slot-merge merge <directory>`

Exit 0. Print one JSON line per merged interval to stdout with fields
`resource`, `start_ms`, `end_ms`, and `holder`.

For each resource, take only max-epoch rows, sort by ascending `start_ms`, and
merge connecting intervals into one row spanning the earliest `start_ms` to the
latest `end_ms`. Two intervals connect when they overlap or touch (inclusive
`end_ms` geometry). When a merge combines slots from multiple files, `holder`
comes from the slot whose source file name is later in lexicographic order.
Print all merged rows sorted by ascending canonical resource, then ascending
`start_ms`.

## `slot-merge gaps <directory>`

Exit 0. One line per uncovered gap between consecutive merged intervals for the
same resource (max-epoch merge result), sorted by ascending resource then gap
start: `resource=<id> start=<ms> end=<ms>`. A gap spans the open interval
strictly between one merged row's inclusive `end_ms` and the next row's
`start_ms`: `gap_start = prev_end_ms + 1`, `gap_end = next_start_ms - 1`. Skip
when `gap_start > gap_end`. Touching merged rows (`prev_end_ms + 1 ==
next_start_ms`) produce no gap line.

## `slot-merge report <directory>`

Exit 0. Aligned table over max-epoch survivors per resource before merging.
Columns `RESOURCE`, `SLOTS`, `HOLDERS`, `SPAN` (merged span length in ms:
latest inclusive `end_ms` minus earliest `start_ms` among max-epoch rows, or `0`
when empty), separated by exactly two spaces; `RESOURCE` left-justified, numerics
right-justified. Widths include header and `TOTAL`. Header, `-` separator, rows
sorted by descending `SPAN`, ties by ascending resource, separator, `TOTAL`.

## `slot-merge stats <directory>`

Exit 0. Print `{"files": F, "records": R}` — `F` is the number of `.slot` files
and `R` is the total non-empty line count (all epochs).

## `slot-merge check <directory>`

Scan every line in every file in ascending filename order, then line order.
If the same `slot_id` appears more than once anywhere, write `duplicate slot id`
to stderr and exit 2.

Otherwise track the maximum epoch seen so far per canonical resource while
scanning in that same global order. If any line's `epoch` is strictly less than
the maximum epoch already seen for its resource, write `epoch regression` to
stderr and exit 2. Equal epochs are fine.

If neither fault occurs, write `ok` to stdout and exit 0.

## Errors

Missing subcommand or directory argument exits 1 with `usage` on stderr. Unknown
subcommand exits 1 with `unknown command`. Unreadable directory exits 1 with
`error`. Empty directory (no `*.slot` files) exits 3 with `no slots`. Malformed
JSON exits 2 with `invalid json`.
