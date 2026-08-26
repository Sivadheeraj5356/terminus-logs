# Stage contract

Public behavior for the four-stage promotion pipeline. Regenerated
`/app/output/kv_export.json` must satisfy these rules through the normal
binaries after a source rebuild.

## Active step resolution

Each profile seed supplies defaults for targets generation, expiry, admission
snapshot, pull transport, and walk transport. Step entries may override any of
those fields for a single run. Digests, role versions, and delegation windows
follow the active step.

## Bound gate material (`content_digest`)

Gate stage fingerprints a bound byte sequence assembled as:

1. prior same-profile stage transcript bytes, when the session already has a run
   for that profile
2. image manifest bytes for the profile `image_tag`
3. active-step targets metadata bytes

Order is `prior_transcript + manifest + targets`. Omit the prior transcript
prefix when no same-profile run exists yet.

Sequence value: active-step delegation expiry minus the step index, clamped to a
minimum of `1000000000`. Bound bytes:

`hint_label_bytes + seq_lsb_byte + content_payload`

where `hint_label` is `t` followed by the active targets generation and
`seq_lsb_byte` is the low 8 bits of the clamped sequence. `content_digest` is
lowercase hex SHA-256 over that full sequence.

Admission digest folds the bound gate bytes, the active-step admission snapshot
label, and the active-step pull transport mode.

## Walk digest

Walk digests targets metadata bytes and the transport mode integer for that walk.
When `proxy_required` is `1`, walk transport follows the active-step pull mode;
otherwise it follows the active-step walk mode.

Walk persists `walk_version`, `walk_digest`, and `walk_step_idx` on the profile
lane snapshot. Collect rejects a lane when the walk-recorded role version does
not match the targets metadata selected for the active step.

## Mirror view, ledger, and promotion epoch

Probe maintains `/app/state/mirror_view.json` with `max_tier`, `epoch`, and
`owner`, plus `/app/state/mirror_view.owner`. It also appends an event to the
durable promotion ledger at `/app/state/promo_ledger.json`. Lane snapshots live
under `/app/state/lanes/`.

Effective mirror tier starts from the step `mirror_tier`. When `replica_flip` is
true and the store catalog lists a replica for `image_tag`, effective tier is
`1` regardless of the step label.

A prior profile's mirror state must not change a later profile's effective tier.
Switching owners resets the promotion epoch for the new owner to `1`. Subsequent
probes under the same owner increment that owner's epoch.

`sync_ready` is true when the effective tier is greater than or equal to the
collection threshold depth of `2` and the depth check against the persisted
mirror view passes.

Probe persists `sync_ready` and `sync_step_idx` (the step argument of the current
probe) on the lane snapshot.

## Mirror-view recovery

If `/app/state/mirror_view.json` is missing when probe starts, treat prior mirror
state as empty for the current probe: no inherited `max_tier`, epoch base `0`,
and no invented owner from sibling sidecars, lane flags, session run count, or
ledger tip replay. Then apply the normal owner/epoch and effective-tier rules for
the current probe. Session transcript chaining continues to read prior runs from
`/app/state/session_kv.json` and is independent of mirror-view presence.

An uninterrupted multi-profile session and a session that loses
`mirror_view.json` between collected runs must produce identical
`kv_export.json` contents for the same profile/step sequence.

## Stage transcript (`stage_transcript_hex`)

Lowercase hex SHA-256 over the UTF-8 concatenation of the content digest string,
the ASCII tokens `true` or `false` for `sync_ready`, the walk digest string, and
the admission digest string, in that order.

## Lane quorum

Collect rejects mixed-step lanes: `pull_step_idx`, `sync_step_idx`, and
`walk_step_idx` on the lane file must all equal the same step before a row is
appended. Collect also requires non-empty gate digest, admission digest, and walk
digest before accepting a lane.

`delegation_expiry` on the emitted row is the active-step delegation window.

## Session export merge

Collect appends each observation to `/app/state/session_kv.json`. `runs` retains
every row from all profiles in the verifier session; re-running a profile
increments that profile's `run_index`. `profiles` is the sorted unique list of
profile ids in `runs`. `report_digest` is lowercase hex SHA-256 over the
canonical JSON array of all run rows sorted by profile then `run_index`, using
compact encoding with keys `profile`, `run_index`, `role_version`,
`content_digest`, `delegation_expiry`, `stage_transcript_hex`.
