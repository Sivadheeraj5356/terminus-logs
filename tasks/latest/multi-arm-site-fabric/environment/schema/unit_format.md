# Sitefab unit and policy file formats

Live install tree expected by `/app/bin/sitefab`:

- `/etc/sitefab/sitefab.conf` — primary INI policy
- `/etc/sitefab/policy.d/*.conf` — lexical merge over the primary file (later names win)
- `/etc/sitefab/templates/<name>.mount` — optional inherit bases for units
- `/etc/sitefab/units/<profile>/<arm>.mount` — systemd-like mount unit per topology arm
- `/etc/sitefab/units/<profile>/<arm>.mount.d/*.conf` — drop-ins merged in sorted filename order

Topology inventories live under `/app/environment/topology/*.json`.
Candidate drops under `/app/environment/drafts/` and `/app/environment/preseed/`
are informal and frequently disagree with production needs.

## Policy sections

```
[Journal]
Path=<absolute journal path>
Carry=<comma-separated persistence keys>

[Digest]
Source=<health-cache|durable-store>

[Reconcile]
Mode=<hand-wins|gen-hand-bs>
RequireDropIns=<yes|no>

[Barrier]
BumpRev=<yes|no>
ClearStale=<yes|no>
CommitPending=<yes|no>
ClearLatch=<yes|no>

[Visibility]
EpochOnRwAfterRo=<yes|no>
OmitStaleRefs=<yes|no>
DependentHold=<immediate|until-propagate>
DependToken=<option token required on dependents, or empty>
MaintLatch=<yes|no>

[Compile]
PreferUnit=<loose|strict>
SealPaths=<yes|no>
```

Known journal carry keys: `epochs`, `last_ro`, `stale_ref`, `pending_arms`,
`latch`. Which subset a site needs depends on its ops tickets.

## Mount unit keys

```
[Unit]
X-Sitefab-Depends=<space-separated arm names>
X-Sitefab-Inherit=<template name without .mount>
X-Sitefab-LinkAfter=<arm that must compile earlier>

[Mount]
What=<backing path>
Where=<mount path>
Type=none
Options=<comma-separated tokens>
X-Sitefab-Remote=<yes|no>
X-Sitefab-OrderHint=<integer>
X-Sitefab-Propagate=<shared|slave|private|rshared|rslave>
```

## Behavioral notes

Remote compile: when `X-Sitefab-Remote=yes`, options containing `_nf` or `nofail`
keep `order_key` equal to the hint; otherwise the controller defers the arm by
ten thousand. LinkAfter peers that still compile at or before the peer hint pick
up an extra five thousand. Unknown propagate tokens add twenty five hundred.
With `SealPaths=yes`, What/Where that do not match the topology inventory also
defer by ten thousand.

Bind-suffix reconcile (`gen-hand-bs`): generator/hand Options pairs may carry
`,bs=<path>`. If only the generator has the marker, append that suffix to the
hand base. If both disagree on the path, keep the hand base and the generator
suffix. When `RequireDropIns=yes`, pending reconcile is taken only from live
`10-generator.conf` / `20-hand.conf` drop-ins for the profile `data` arm;
topology `units` rows are not a silent fill-in.

Dependent hold: with `DependentHold=until-propagate`, a primary `rw` that follows
`ro` marks units listing that primary in `X-Sitefab-Depends` as stale until a
`prp` step targets the dependent arm. When `DependToken` is set, the dependent
unit Options must include that exact token or the hold is skipped.

Maintenance latch: with `MaintLatch=yes`, bind-move (`bmv`) steps record latch
marks that persist when `latch` is carried. Barrier clears them only when
`ClearLatch=yes`.
