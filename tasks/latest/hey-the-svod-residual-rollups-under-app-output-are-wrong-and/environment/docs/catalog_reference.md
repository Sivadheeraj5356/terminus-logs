# Catalog reference

## Works CSV

Path: `/app/data/works.csv`

Header: `workId,titleAlias,status`

`status` must be `active` or `inactive`. Events referencing inactive works are excluded.

## Aliases CSV

Path: `/app/data/aliases.csv`

Header: `alias,workId`

Matching is case-insensitive on `alias`. Resolve `workAlias` from usage feeds to `workId` through this table. Unknown aliases exclude the event.

## Participants CSV

Path: `/app/data/participants.csv`

Header: `workId,participantId,weight,catalogIndex`

- `weight` is a positive integer split weight
- `catalogIndex` is a non-negative integer used for remainder ordering (see `allocation_contract.md`)

Only participants listed for a `workId` receive escrow allocations.

## Ingest manifest tie-break

When two usage rows tie on revision and `capturedAt`, the row from the file with the **higher index** in `usage_ingest_order.json` wins — not lexicographic path order.

Example: if `files` is `["data/usage/b.jsonl", "data/usage/a.jsonl"]`, then `a.jsonl` has manifest index 1 and `b.jsonl` has index 0; a tie goes to `a.jsonl`.
