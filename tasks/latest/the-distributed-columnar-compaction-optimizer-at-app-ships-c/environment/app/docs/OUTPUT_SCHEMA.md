# Merge plan JSON schema

All successful commands emit compact JSON with stable key ordering as produced by report.cpp.

## Plan object

Fields: fragment_ids, row_overlap_lengths, total_rows, scan_cost_units, fragmentation_index, replica_consistent, fingerprint.

fragmentation_index follows the missing-row width sum defined in /app/docs/SCAN_COST.md.

## Validation object

Fields: ok, primary_error, errors, fingerprint.

## Repair object

Fields: ok, primary_error, swaps, fingerprint.

## Plan signature and fingerprint

Build a signature string:

```
rows:<total_rows>;cost:<scan_cost_units>;frag:<id1>,<id2>,...;rep:<0|1>
```

Apply FNV-1a 64 over the signature bytes (offset basis 1469598103934665603, prime 1099511628211), then the splitmix64 finalizer:

```
x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9
x = (x ^ (x >> 27)) * 0x94d049bb133111eb
x = (x ^ (x >> 31))
```

Render the lower 64 bits as 16 lowercase hexadecimal digits.
