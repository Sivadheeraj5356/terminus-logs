# Bootyard Custody and Generation Protocol

Clause namespace: `YARD-*`

This contract defines the closed captured-host model for `.bootyard` and `.bootorder` directories. It is not a full description of live systemd on a running machine. Evaluator host paths outside the supplied yard are never consulted.

## YARD-1 Yard identity

`yard.identity` is UTF-8 text, LF-terminated, BOM/NUL-free. Records are `key=value` lines in a fixed key order:

```
format=bootyard.v1
host_label=<ascii_id>
machine_id=<32 lowercase hex>
architecture=<x86_64|aarch64|armv7l|riscv64>
initial_generation=<nonnegative integer without leading zeros except 0>
default_target=<unit name ending .target>
admin_roots=etc/systemd/system
max_unit_files=<1..160>
max_dropins=<1..240>
max_admin_symlinks=<1..260>
max_devices=<1..120>
max_directives=<1..4000>
max_arcs=<1..2000>
max_intent_ops=<1..48>
max_targets=<1..12>
max_yard_bytes=<1..8388608>
previous_state=<comma-separated roster or empty>
immutable_digest=<64 lowercase hex>
```

`immutable_digest` commits, in this order, the logical bytes of `vendor.seal`, `runtime.facts`, `proc.cmdline`, `devices.table`, and every regular file and relative symlink under `usr/lib/systemd/system/` and `run/systemd/system/`, walking depth-first by raw ASCII path. Absolute yard location, inode, owner, mtime, and directory enumeration order must not affect the digest.

## YARD-2 Vendor seal and runtime facts

`vendor.seal` lists one line per member under `usr/lib/systemd/system/`:

```
<path>\t<file|symlink|absent>\t<mode octal or ->\t<sha256 or link text or ->
```

Paths are relative to that tier root, without `.` or `..`. Modes for regular files are `0644` or `0755`. Symlink targets are relative or exactly `/dev/null`.

`runtime.facts` is a typed table with keys: `architecture`, `virtualization`, `firmware`, `hostname`, `machine_id`, `boot_id`, `first_boot`, `env_flags`, then zero or more `path_fact=<path>\t<missing|file|dir|symlink>` and `mount_fact=<path>\t<fstype>`. Values are canonical; booleans are `true` or `false`.

`proc.cmdline` is a single line `cmdline=<tokens>` where tokens are space-separated and sorted only when the capture declares `sorted=true` on a preceding metadata line; otherwise token order is preserved exactly as captured.

## YARD-3 Device table

`devices.table` maps device unit names:

```
<device.unit>\t<ready|absent>\t<backing_id>\t<alias,alias,...>
```

Aliases may include `uuid:<hex>`, `label:<ascii>`, and `dev:<name>`. Conflicting backing identities for one alias, or alias cycles, invalidate custody. Ready devices may contribute device jobs; absent required devices produce documented mount failure. The evaluator `/dev` tree is never read.

## YARD-4 Bootorder members

A `.bootorder` directory contains exactly `order.record`, `unit.intent`, `preset.selection`, `acceptance.jobs`, and `order.seal`. All are UTF-8, LF-terminated, comment-free.

`order.record` keys in order: `format=bootorder.v1`, `order_id`, `yard_host_label`, `yard_machine_id`, `expected_generation`, `next_generation`, `final_target`, `job_mode` (`fail` or `replace`), bounds echoing the yard ceilings, and `members_digest` over the other four members in fixed name order.

`next_generation` must equal `expected_generation + 1`. `order_id` must not appear in any prior accepted record under `var/lib/unitgraph/`.

## YARD-5 Intent, preset, acceptance

`unit.intent` is an ordered list, one operation per line:

```
<seq>\t<ENABLE|DISABLE|MASK|UNMASK|PRESET|SET_DEFAULT|PUT_DROPIN|REMOVE_DROPIN>\t<unit>\t<instance or ->\t<prestate>\t<payload_digest or ->\t<expected_class>\t<payload_fields or ->
```

`preset.selection` lines are `enable|disable|ignore <pattern>` in first-match order. `acceptance.jobs` lines are:

```
<unit>\t<STARTED|SKIPPED|FAILED>\t<public_reason>
```

plus optional `target_member=<unit>` lines listing final target membership. Acceptance cannot dictate internal traversal order.

## YARD-6 Mutable surfaces and generation

Only `etc/systemd/system/` and `var/lib/unitgraph/` may change on success. Vendor, transient, identity, seals, facts, cmdline, and devices are immutable. Before any write, snapshot the mutable trees. Stage into a private sibling shadow, cold-replay, then exchange. Any fault restores every preexisting byte, link target, mode, and absence.

`var/lib/unitgraph/generation` holds the canonical decimal generation. An order whose `expected_generation` matches the current generation and whose `order_id` already appears in `accepted.order` is a verified no-op that reprints the prior receipt. Stale or skipped generations reject without mutation.

## YARD-7 Path and operand rules

Administrator operands are two absolute normalized paths ending `.bootyard` and `.bootorder`. Reject symlinked roots, lexical escape, `.`/`..` segments, control bytes, repeated separators, aliasing between roots, extra arguments, and an order stored beneath the yard. Success stdout is one lowercase SHA-256 receipt and a single LF.

## YARD-8 Closed-model omissions

This model omits live unit dbus APIs, generator execution, `Exec*` process launch, real mount(2), udev, and evaluator environment variables. Those omissions are intentional.
