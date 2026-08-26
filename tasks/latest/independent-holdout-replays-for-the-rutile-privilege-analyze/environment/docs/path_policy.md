# Path policy

Escalation paths are shortest routes on the combined directed graph from each analysis entry to each crown target.

`hop_count` records one less than the number of nodes on the path. Severity tiers for a chain derive from `hop_count` and the inclusive ceilings declared under `[thresholds]` in `/app/environment/config/severity.toml`.

Chain rows sort by entry identifier, then target identifier.
