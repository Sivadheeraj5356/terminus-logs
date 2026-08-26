# Compaction contract

Tool: /app/columnarctl

## Invocation and exit status

Running /app/columnarctl with no arguments, or with a first token that is not a known subcommand, prints exactly USAGE on stderr and exits with status 2.

For recognized subcommands, a non-zero exit status always accompanies exactly one error token on stderr (no extra prose). Common tokens include CATALOG_ERROR, STAGING_ERROR, STALE_SNAPSHOT, ORDER_VIOLATION, OVERLAP_CONFLICT, FINGERPRINT, REPLICA_MISMATCH, and the validation primary_error values listed below. Successful validate and repair print one JSON object on stdout and exit 0.

## Subcommands

- ingest --catalog PATH --policy PATH [--snapshot PATH]
- export --catalog PATH --policy PATH --out PATH [--snapshot PATH]
- plan --catalog PATH --policy PATH --out PATH
- validate --plan PATH --catalog PATH [--policy PATH]
- repair --plan PATH --catalog PATH --out PATH [--policy PATH]

ingest writes a staging snapshot per /app/docs/STAGING_SNAPSHOT.md. export requires a valid snapshot and emits the merge plan JSON. plan performs ingest then export atomically for the same catalog and policy.

Successful validate and repair print one JSON object on stdout.

## Catalog input

Fragment catalogs use the CLFC binary format documented in /app/docs/CATALOG_FORMAT.md. Parsed fragments carry id, partition_id, seq, flags, row_start, row_end, byte_size, replica_mask, column_name, and a normalized column name used for partition matching.

flags bit 0 marks an anchor fragment eligible as a chain start. When multiple anchors exist, pick lowest seq, then lowest id.

## Column normalization

Before row overlap comparison, each column_name must be normalized per /app/docs/CATALOG_FORMAT.md: remove embedded NUL (0x00) bytes, strip BOM, trim whitespace, collapse internal whitespace, optional ASCII case fold from policy.

## Row overlap graph

Directed edge A to B exists when both fragments share partition_id and normalized column_name, and their inclusive row ranges overlap by at least min_row_overlap rows.

When choosing the greedy successor from the current fragment:

1. Maximize row overlap length.
2. Tie-break by lowest target seq.
3. Then lowest target id.

Start fragment selection:

1. Anchored fragments (flags bit 0), lowest seq then id.
2. Else fragments with no incoming overlap edge, same tie-break.
3. Else lowest seq among all fragments.

## Merge plan JSON

See /app/docs/OUTPUT_SCHEMA.md. total_rows counts merged row coverage after subtracting junction overlaps. row_overlap_lengths[i] is the junction overlap between fragment_ids[i] and fragment_ids[i+1].

## Scan cost and fragmentation

scan_cost_units and fragmentation_index follow /app/docs/SCAN_COST.md. replica_consistent follows /app/docs/REPLICA_POLICY.md.

## Fingerprint

Each plan carries a fingerprint derived from a canonical plan signature string. The algorithm is specified in /app/docs/OUTPUT_SCHEMA.md.

## Validation error priority

When multiple errors apply, primary_error is first in this order; errors lists all detected tokens sorted the same way:

1. CATALOG_ERROR
2. DUPLICATE_ID
3. OVERLAP_CONFLICT
4. ORDER_VIOLATION
5. OVERLAP_TOO_SHORT
6. GAP_DETECTED
7. COVERAGE
8. FINGERPRINT
9. AMBIGUITY
10. REPLICA_MISMATCH
11. SCAN_COST
12. FRAGMENTATION

Meaning:

- OVERLAP_CONFLICT — a plan junction uses an overlap shorter than the maximum row overlap available between that fragment pair.
- AMBIGUITY — a plan successor is not the greedy choice selected by the tie-break rules at maximum overlap length.
- REPLICA_MISMATCH — replica_consistent flag does not match catalog replica masks under policy.
- SCAN_COST — scan_cost_units does not match the contract formula.
- FRAGMENTATION — fragmentation_index does not match missing-row width accounting in /app/docs/SCAN_COST.md.

## Repair rules

repair rebuilds the plan using the same planning algorithm. It is idempotent on already-valid plans (swaps = 0). If validation still fails after repair, exit non-zero with primary_error and do not write --out.
