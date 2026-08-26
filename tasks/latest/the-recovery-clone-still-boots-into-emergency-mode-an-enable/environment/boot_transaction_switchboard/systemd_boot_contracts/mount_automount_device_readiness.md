# Mount, Automount, and Device Readiness

Clause namespace: `MOUNT-*`

## MOUNT-1 Mount unit names

Validate mount unit names against decoded `Where=` paths. Root maps to `-.mount`. Other absolute normalized paths use the escape law from `SPECIFIER-3`. A mismatched fragment name and `Where=` is invalid; do not repair heuristically.

## MOUNT-2 Parent mounts

Create implicit parent-mount dependencies when a mount's `Where=` has a parent path that corresponds to another mount unit in the transaction or effective set, exactly when the parent path is not `/`. Record origin `default:parent-mount`.

## MOUNT-3 What and devices

Interpret `What=` only through `devices.table` and supported stable alias forms (`uuid:`, `label:`, `dev:`). A ready device contributes a device job and ordering. An absent required device yields mount result `FAILED` with public reason `device-absent`. Never inspect real block devices, `/proc`, `/sys`, fstab, udev, or evaluator mounts.

## MOUNT-4 Device alias identity

Aliases resolving to one backing identity deduplicate to a single device job. Conflicting identities or alias cycles fail custody validation before mutation. Deduplicate by backing identity, not by alias spelling alone.

## MOUNT-5 Automount coupling

An automount and its corresponding mount form a coupled pair without a start-order loop. Starting the automount does not activate the mount payload. Acceptance records may declare `access_trigger=<automount.unit>`; only that trigger activates the mount job in the boot trace. Parent automounts and idle-independent fixture behavior follow the semantics capsule; readiness is recorded in `boot.trace`.

## MOUNT-6 Service gating

Mount availability gates services that explicitly `Requires`/`After`/`RequiresMountsFor`-style admissible directives against the mount unit. Do not infer service path dependencies from arbitrary command-line strings.

## MOUNT-7 Neutral example

`Where=/data` requires unit name `data.mount`. `Where=/` requires `-.mount`. Alias `uuid:abcd` and `dev:disk1` sharing backing `bk1` produce one device job.

## MOUNT-8 Omissions

This document omits NFS `_netdev` heuristics beyond the fstype class flag in facts, overlay option parsing, and live automount idle timeouts.
