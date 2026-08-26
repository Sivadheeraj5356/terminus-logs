# Merge deduplication

Merge collapses records sharing `(scope_id, action_mask)` keeping the entry with the highest `rotate_gen`. Ties on generation prefer the lexicographically later journal filename. Output order follows first-seen key order.
