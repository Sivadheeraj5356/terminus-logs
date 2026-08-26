# Failback convergence coordination

Maintenance returns on the wp-maint profile coordinate neighbor replay,
endpoint attach, publish barriers, and dual-authority epoch agreement before
cycle records are emitted.

## Dual-signal convergence

Role completion and announcement completion each close independently during a
maintenance return. Coordination that finalizes the maintenance cycle must
observe both closures, regardless of which closes first.

## Epoch-scoped attach latch

For a given generation epoch, endpoint attach must not be recorded complete
while neighbor replay for that epoch is still pending. Replay completion must
not be inferred from attach latch advancement. Attach latch advancement with
no pending attach for the epoch must not fabricate completion.

## Publish barrier hold

Queued publish frames for an epoch must not be released until the publish
barrier closes. Release must reject epochs with no queued frame, empty
payloads, or payloads larger than 1500 bytes. After a valid release, replay
completion tick reflects the simulation clock at release.

## Journal generation reconciliation

After reopen, persisted journal entries below the active forwarding epoch must
be removed before the next maintenance return.
