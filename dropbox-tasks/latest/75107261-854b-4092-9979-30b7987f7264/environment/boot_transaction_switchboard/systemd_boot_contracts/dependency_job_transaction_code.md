# Dependency Job Transaction Code

Clause namespace: `JOB-*`

## JOB-1 Transaction seed

Construct the final target's start transaction from post-mutation effective units. Install links become runtime dependencies only when they appear as symlinks in the selected target's active `.wants/` or `.requires/` directories under the administrator tier (and equivalent transient/vendor install directories when present in the closed yard).

## JOB-2 Edge kinds

| Directive | Pulls start job | Failure propagation | Notes |
|---|---|---|---|
| `Wants` | yes | non-fatal | owner may start if wanted fails |
| `Requires` | yes | fatal | owner fails if required fails |
| `Requisite` | no pull if inactive | fatal if inactive/fail | peer must already be active in captured initial state |
| `BindsTo` | yes | fatal + inactive propagation | requirement plus stop when bound peer stops |
| `PartOf` | no initial start requirement | stop/restart propagation recorded | not a start pull |
| `Conflicts` | may add stop job | — | not a start dependency |
| `Before`/`After` | never pulls | — | orders jobs already present |

## JOB-3 Default dependencies

Unless `DefaultDependencies=no`, synthesize typed default edges:

- services: after `basic.target` (logical), before `shutdown.target` stop ordering when modeled
- targets: after `basic.target` unless the target is `basic.target` or `paths.target` special cases listed in the semantics capsule
- mounts: before `local-fs.target` or `remote-fs.target` by fstype class from facts; after parent mounts
- automounts: before `local-fs.target`; coupled to mount without start-order loop
- paths: before `paths.target`
- devices: before `sysinit.target` when pulled

Every synthesized edge records origin `default:<rule>`. Explicit and synthesized provenance must remain distinct.

## JOB-4 Job mode and conflicts

`job_mode=fail` rejects conflicting start/stop merges that cannot be reconciled. `job_mode=replace` allows stop jobs from `Conflicts` to replace competing starts per capsule rules. Requirement impossibility is detected separately from ordering cycles.

## JOB-5 Ordering cycles

On an ordering cycle, remove only contract-permitted synthesized edges in priority: default-deps first (lowest retention), then implicit parent-mount edges, never explicit directive edges. Emit a canonical witness listing removed edges sorted by unit-name pairs. An all-explicit irreducible cycle rejects the order with that witness.

## JOB-6 Stability

Where the contracts leave a true tie, use stable unit-name ASCII order. Hash-map iteration, directory order, request order, fragment tier, and insertion order must not silently become graph semantics.

## JOB-7 Transaction jobs record

`transaction.jobs` accounts for every pulled, merged, stopped, skipped, failed, or excluded job and each originating edge with provenance.

## JOB-8 Omissions

This code omits job engines for sockets, timers, swaps, scopes, slices, and systemd transient bus jobs.
