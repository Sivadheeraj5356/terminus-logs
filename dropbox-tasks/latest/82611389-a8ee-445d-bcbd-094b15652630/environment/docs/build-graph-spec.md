# Build graph specification

Manifest CSV columns: module_id,version,depends_on.

Topological ordering must use Kahn's algorithm with stable tie-breaking:

1. Sort the initial ready set ascending by module_id.
2. On each dequeue, collect newly unlocked modules, sort THAT batch ascending by module_id, then append the batch to the tail of the queue.
3. Do not re-sort the entire remaining queue after each unlock.

Reject cycles with error cycle_detected. Reject unknown dependency IDs with error manifest_error.

Semver comparisons must be numeric on major.minor.patch tuples.

For the default acyclic manifest at /app/data/module-manifest.csv, the build plan order must be:

auth-core → billing-api → ingest-worker → notify-hub → gateway

Alternate manifests (cycle, unapproved, low-version, high-version, tiebreak, diamond, missing-dep) are documented in /app/docs/module-fixture-index.md.
