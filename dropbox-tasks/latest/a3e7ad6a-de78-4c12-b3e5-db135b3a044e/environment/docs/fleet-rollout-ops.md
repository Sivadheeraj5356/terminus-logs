# Fleet rollout operations

System-administration operators treat each decision impact plan as a fleet config rollout artifact.

## Rollout ordering

The execution_order field is the daemon-safe rollout sequence for coordinated unit changes. Topology drift appears when exclusive windows collide on shared units after impact fan-out.

## Drift report coupling

Conflicts of type timeline encode topology drift between exclusive decisions. Resource conflicts encode pool contention during the same rollout window.

## Lifecycle

Stage builds the lattice snapshot used by plan. Plan must not reopen scenario fixtures, mirroring a daemon that only reads the staged fleet config snapshot. Operators may keep a separate parked copy of scenario files for review, but plan must still consume only the staged lattice path supplied on the CLI.

Lattice digests are 64-character lowercase hexadecimal witnesses of the staged fleet snapshot.

Rollout epoch seals, journal appends, and supersession refusal are defined in /app/docs/rollout-epoch-seal-contract.md.
