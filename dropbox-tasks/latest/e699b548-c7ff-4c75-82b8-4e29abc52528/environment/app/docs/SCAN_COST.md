# Scan cost accounting

scan_cost_units measures read amplification for executing the merge plan.

## Formula

1. Sum byte_size for every fragment listed in fragment_ids.
2. Multiply the sum by policy scan_cost_per_byte.
3. Add fragmentation_index multiplied by policy scan_penalty_per_gap.

All arithmetic uses 64-bit unsigned accumulation in the implementation.

## fragmentation_index

Walk fragment_ids in plan order. For each consecutive pair (A, B), when B row_start is strictly greater than A row_end plus one, add the missing row width to a running total:

missing_rows += B row_start - A row_end - 1

When total_rows is zero, fragmentation_index equals missing_rows (the width sum).

Otherwise fragmentation_index equals (missing_rows multiplied by 1000) divided by total_rows using integer division toward zero.

This uses the sum of hole widths between consecutive fragments, not the count of gap occurrences. Two catalogs with the same total missing row span but different gap counts must yield the same fragmentation_index.

scan_penalty_per_gap scales the finished fragmentation_index value; it is not multiplied by a separate gap count.
