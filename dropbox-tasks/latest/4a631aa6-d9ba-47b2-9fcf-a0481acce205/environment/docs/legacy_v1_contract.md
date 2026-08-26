# Legacy v1 contract (obsolete)

This document is retained only for audit history. Do not implement these rules for the current task.

The legacy processor loaded usage shards lexicographically, ignored `revision`, used floating-point accrual, and emitted pretty-printed escrow JSON. Those behaviors are incompatible with the current contracts in `usage_feed_contract.md`, `rate_and_recoupment.md`, `allocation_contract.md`, and `output_contract.md`.
