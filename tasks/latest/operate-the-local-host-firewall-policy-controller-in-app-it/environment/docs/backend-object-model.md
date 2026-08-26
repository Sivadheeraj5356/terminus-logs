# Backend object model

The simulator stores sets, chains, and rules in `backend.json`. Rules expose handles for evaluation order and counters.

Operator-created rules omit managed annotations or set `managed: false`. Daemon-managed rules include managed annotations and manifest entries.

Visible names are labels derived from object kind, id, and semantic revision. Collisions are possible when revision hashes truncate. Foreign operator rules may use visible names such as `operator-collision-demo` that resemble managed prefixes without sharing ownership.
