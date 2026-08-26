# Image-Rendering Lab Diagnostic Workstation Compliance Postmortem

This document is the consolidated postmortem covering the 2026-Q1 compliance
regression on the image-rendering diagnostic workstation fleet. It supersedes
every prior IR/RCA that touched the render-a, render-b, and render-c racks and
is now the sole reference for how the fleet must be brought back into a state
where Valgrind and gdb sessions can attach to the media pipeline processes
without leaving the host in an unsafe core-dump posture. Every classification
rule the compliance team enforces is documented here. If you cannot find a
rule in this document you cannot enforce it; the compliance owner will reject
any Rego library that acts on undocumented signals.

The postmortem is organized into eleven sections. Section 1 explains why the
regression occurred and how the debugger-attach failures interact with the
core-dump posture. Section 2 documents the fleet baseline captured by the
inventory sweep on 2026-02-11. Section 3 through Section 9 each describes a
single family of remediation actions: sysctl, systemd drop-in, group
membership, ulimit configuration, filesystem permissions, immutable
attribute clearance, and fixture permission normalization. Section 10 pulls
the individual rules together into the ordered decision matrix that the
Rego library must reproduce. Section 11 records the operational review, the
open questions we intentionally deferred to a follow-up postmortem, and the
non-goals that are explicitly out of scope for the remediation.

Read every section. Each of Sections 3 through 9 states, in prose, the exact
condition under which its action must appear in the plan for a workstation
and gives the exact action string. Section 10 restates the ordering. If you
believe two sections contradict, Section 10 is authoritative: the ordering
listed there is the ordering the plan must use.

Nothing in this document requires the reader to trust an out-of-band source.
Every fact used to derive the decision matrix is either in the inventory (a
DuckDB database committed alongside this document) or restated in the prose
below. Where a section refers to `mediauser`, `media`, `debug`, or
`/var/lib/media/scratch`, those names are load-bearing: they appear verbatim
in the emitted action strings and must not be substituted, aliased, or
inferred.

## Section 1 -- Why the regression happened

The image-rendering lab operates ten diagnostic workstations across three
racks. Racks A and B are conventional Intel and AMD x86_64 systems running a
6.6-series Debian kernel. Rack C runs Apple Silicon hosts on a 6.7-series
downstream kernel. The workstations exist so that whenever a media pipeline
process misbehaves on a production render node, an on-call engineer can pull
the failing fixture down to a diagnostic host, attach Valgrind or gdb to a
reproducer, and produce an actionable trace within the same shift. That
workflow is the entire point of the lab; every configuration decision below
serves it.

The regression that triggered this postmortem started in mid-January 2026.
An on-call engineer attempted to attach Valgrind to a live reproducer for a
TIFF decoder crash and was refused with `PTRACE_ATTACH: Operation not
permitted`. Over the following two weeks the same error appeared on six
different workstations, sometimes for gdb, sometimes for Valgrind, sometimes
for both. In parallel the systems engineering team noticed that four of the
workstations had started writing core files to unexpected locations (a
custom `core_pattern` had been silently reverted), and two workstations had
begun blocking core dumps for set-user-id executables entirely by lowering
`fs.suid_dumpable` to zero. The lab is authorised to permit core dumps for
suid binaries because the media pipeline runs a single set-user-id shim for
GPU device access; without those dumps, the shim cannot be diagnosed.

We traced every symptom to a policy drift caused by the November 2025 image
refresh. The refresh brought new defaults for `kernel.yama.ptrace_scope`,
`kernel.core_pattern`, `fs.suid_dumpable`, `systemd-coredump`,
`/etc/security/limits.d`, `/var/lib/media/scratch` filesystem permissions,
and the `mediauser` group memberships. Individually, each default is a
sensible hardening choice; collectively they made the diagnostic workflow
impossible. The refresh also introduced a new `chattr +i` immutable
attribute on the scratch directory of one rack, which the operations team
had not previously seen and which broke core dumping outright on that host.

The compliance regression is therefore not a security regression -- it is a
diagnostic-workflow regression that the refresh caused by hardening beyond
what the lab charter allows. Rolling back the refresh is not an option:
production nodes now depend on the newer image for unrelated reasons. The
remediation is to re-open the specific holes the diagnostic workflow needs,
in a controlled way, and to encode those exceptions in a Rego library that
the compliance scanner can read directly. That library is the deliverable.

The eleven-section structure of this postmortem exists so that a reader can
skip to a specific action family, confirm the exact rule, and translate it
into Rego. Sections 3 through 9 each describe exactly one action family and
give the emit condition and the exact action string. Section 10 gives the
canonical ordering for the emit sequence.

## Section 2 -- Fleet baseline captured on 2026-02-11

The inventory sweep on 2026-02-11 covered every diagnostic workstation. The
raw data is in the DuckDB file `inventory/workstations.duckdb` and the seed
CSV `inventory/workstations.csv`. Ten workstations are in scope: ws-001
through ws-010. Each row records the workstation identifier, hostname, chip
family (`intel`, `amd`, or `apple-silicon`), kernel release, fixture
workload (`tiff`, `png`, or `mp4`), the current value of
`kernel.yama.ptrace_scope`, the current value of `kernel.core_pattern`, the
current value of `fs.suid_dumpable`, whether an override file for
`systemd-coredump` is present in `/etc/systemd/coredump.conf.d/`, whether
`mediauser` is in the `debug` group, whether `mediauser` is in the `media`
group, the soft and hard `RLIMIT_CORE` values, the octal mode string, owning
user, and owning group of `/var/lib/media/scratch`, and whether the immutable
attribute `+i` is set on `/var/lib/media/scratch`.

The purpose of this postmortem is not to explain how those facts were
gathered; the sweep tooling was archived on the operations wiki. What matters
is that the DuckDB is the ground truth. When a Rego rule refers to the
current value of `ptrace_scope` for a workstation, it means the value in the
`workstations` table for that workstation identifier, projected through the
`v_workstation` view onto the JSON key `ptrace_scope`. The harness
`harness/load_facts.py` performs that projection and emits the workstation
row as a single-object JSON document under the key `workstation`. The Rego
library reads it as `input.workstation`.

There are ten workstations in scope. Every workstation in scope is
classified by the same set of rules described in Sections 3 through 9. There
is no workstation exception list: if a workstation appears in the DuckDB it
is subject to the full decision matrix. A workstation that is fully
compliant on every rule still emits a plan containing at least one action
(the fixture permission normalization from Section 9), so an empty
`actions` array in a plan is always incorrect.

## Section 3 -- kernel.yama.ptrace_scope

The Yama LSM enforces `kernel.yama.ptrace_scope` at four levels. Level 0
allows any process to ptrace any other that it owns. Level 1 restricts
ptrace to a parent process only, which is the Debian default and is what
broke Valgrind. Level 2 restricts ptrace to root only. Level 3 disables
ptrace entirely and requires a reboot to change.

The diagnostic workstations must run at `kernel.yama.ptrace_scope=0`.
Valgrind and gdb both use the `ptrace(PTRACE_ATTACH, ...)` system call to
attach to a running reproducer, and the on-call engineer will typically be
attaching from a user session, not from a parent shell of the target
process. Level 1 refuses that attachment. Level 2 refuses it as well
because the on-call engineer is not root. Level 3 refuses it and cannot be
temporarily relaxed without a reboot, which is not acceptable during an
incident.

The remediation rule for this family is: emit the action
`sysctl:kernel.yama.ptrace_scope=0` if and only if the current value of
`ptrace_scope` for the workstation is not zero. If the current value is
already zero, do not emit the action. There is no partial state: three of
the four Yama levels require the same remediation and there is no per-user
Yama override the lab charter permits.

The exact action string is `sysctl:kernel.yama.ptrace_scope=0`. Do not
introduce whitespace, do not capitalise, do not append a semicolon, do not
substitute `=` with `:` or `->`. Downstream tooling parses the string with a
strict prefix match and a suffix comparison and will treat any variant as a
different action.

There is an important non-goal here. The remediation only relaxes
`kernel.yama.ptrace_scope`. It does not touch `kernel.perf_event_paranoid`,
`kernel.kptr_restrict`, or `kernel.unprivileged_userns_clone`. Those three
sysctls appeared in early drafts of this postmortem and were removed on
2026-02-25 because Valgrind and gdb do not require them for the fixture
workloads in scope. If a Rego rule emits a sysctl action for any of those
three keys, the reviewer will reject the submission as out of scope.

The action's position in the plan is fixed. Section 10 documents that
`sysctl:kernel.yama.ptrace_scope=0` is the first action to be emitted when
present. The reason for the position is operational: relaxing ptrace_scope
takes effect immediately and does not require any dependent state, so it
should be applied first to unblock the debugger regardless of whether the
downstream actions succeed.

## Section 4 -- kernel.core_pattern

The `kernel.core_pattern` sysctl controls where a crashing process writes
its core file. The lab charter requires the value `core`, which causes the
kernel to write a file named `core` in the current working directory of the
crashing process. The default on Debian is `|/bin/false`, which pipes the
core to `/bin/false`, which discards it. That default is the safest possible
choice for a shared multi-tenant host, and the correct choice for a
production render node; it is the wrong choice for a diagnostic
workstation because a discarded core cannot be inspected in gdb after the
fact. Two of the workstations were also observed with the systemd-coredump
handler string `|/usr/lib/systemd/systemd-coredump ...` before the November
refresh; the refresh replaced that with `|/bin/false` outright.

The remediation is: emit the action
`sysctl:kernel.core_pattern=core` if and only if the current value of
`core_pattern` is not the exact string `core`. Any other value -- the
`|/bin/false` default, the systemd-coredump handler string, an absolute
path, or an empty string -- triggers the action.

The exact action string is `sysctl:kernel.core_pattern=core`. Match the
same lexical rules as Section 3. Note in particular that the value string
is `core`, not `%e.core`, not `/var/lib/media/scratch/core`. The lab
originally considered an absolute-path pattern to steer cores into the
scratch directory but rejected it on 2026-01-30 because the crashing
processes already run with the scratch directory as their working
directory during a diagnostic session; writing to `.` from within the
scratch directory is equivalent to writing to
`/var/lib/media/scratch/core` and is easier to reason about.

The position of this action in the plan is second when present, immediately
after the ptrace_scope action. The reason is that both are sysctl actions
applied through the same `sysctl -w` invocation in the eventual
remediation runbook, and grouping them keeps the runbook diff minimal.

Do not emit this action for a workstation whose current `core_pattern` is
already `core`. Six of the ten workstations in the inventory already have
the correct value; issuing a no-op sysctl write on those hosts triggers a
compliance false positive because the change tracker interprets it as
active drift.

## Section 5 -- fs.suid_dumpable

The `fs.suid_dumpable` sysctl controls whether set-user-id executables
produce a core dump on crash. Value zero disables core dumps for suid
binaries entirely. Value one enables them but writes them owned by root
mode 0600, which is not useful for a user-space diagnostic workflow.
Value two enables them and writes them owned by root with a mode derived
from `fs.suid_dumpable_ownership`; on the diagnostic workstations we
configure that to allow the debug group to read the resulting cores.

The lab charter requires `fs.suid_dumpable=2`. This is the only value
that lets the on-call engineer read a core dump from the set-user-id GPU
shim without escalating to root.

The remediation is: emit the action
`sysctl:fs.suid_dumpable=2` if and only if the current value of
`suid_dumpable` for the workstation is not two. Both zero and one trigger
the action.

The exact action string is `sysctl:fs.suid_dumpable=2`. The value must
be the ASCII digit `2`. Do not spell it out, do not substitute `two`, do
not use a leading zero.

The action's position in the plan is third when present, after the
ptrace_scope and core_pattern actions. All three sysctls are applied
through the same `sysctl -w` invocation.

There is a deliberate omission in this section. The postmortem does not
require any change to `kernel.core_uses_pid`, which controls whether the
crashing PID is appended to the core filename. That sysctl is left at its
Debian default of one on every workstation because the diagnostic
workflow keys off timestamps and hostnames, not PIDs. If a Rego rule
emits a sysctl action for `kernel.core_uses_pid`, the reviewer will
reject the submission for the same reason as in Section 3.

## Section 6 -- systemd-coredump drop-in

Bookworm ships systemd-coredump, a userspace helper that intercepts
kernel core dumps and stores them under `/var/lib/systemd/coredump/`.
The lab charter requires that we override two of its defaults on the
diagnostic workstations: `Storage=external` (the default) is fine, but
`ProcessSizeMax` must be raised to a value large enough to capture the
memory footprint of a 4K TIFF decoder (2 GiB), and the `MaxUse` disk
budget on the coredump storage directory must be raised from 10% of the
device to 40%. Neither change is safe on a shared production host; both
are necessary on a diagnostic workstation.

The mechanism for applying these overrides is a systemd drop-in file at
`/etc/systemd/coredump.conf.d/media.conf`. The presence of the file
indicates that the overrides have been applied; the absence of the file
indicates the workstation is running with the stock Bookworm defaults and
that a diagnostic dump larger than a few hundred megabytes will be
truncated. The inventory records a boolean `coredump_conf_present` for
each workstation.

The remediation is: emit the action
`systemd:/etc/systemd/coredump.conf.d/media.conf` if and only if
`coredump_conf_present` is false for the workstation. If the drop-in
already exists, do not emit the action; the compliance scanner assumes
the file is a signal that the lab-approved content is present, and does
not attempt to hash the file.

The exact action string is
`systemd:/etc/systemd/coredump.conf.d/media.conf`. Note the prefix
`systemd:` and the absolute path. Do not shorten the path, do not use a
relative path, do not substitute `.d/media.conf` with `.d/lab.conf` or
any other filename. The `media.conf` name is the load-bearing convention
across the fleet.

The action's position in the plan is fourth when present, after the three
sysctl actions and before the group-membership actions. The reason is
operational: the drop-in requires a `systemctl daemon-reload` to activate,
which is an idempotent no-op if the file is absent, so we apply the
drop-in before adjusting group memberships that may be needed to read the
resulting coredump directory.

## Section 7 -- group memberships for mediauser

The `mediauser` account is the on-call debug identity on every diagnostic
workstation. It must be a member of two groups. The `debug` group grants
read access to the systemd-coredump directory and to the ptrace-trace
files. The `media` group grants read/write access to the media pipeline
scratch directory `/var/lib/media/scratch`. Both memberships are required
for a productive debugging session.

The inventory records two booleans, `in_debug_group` and
`in_media_group`, for each workstation. Neither membership implies the
other; the November refresh reset both to false on some workstations and
one of the two on others.

The remediation is two actions. Emit `group:add:mediauser:debug` if and
only if `in_debug_group` is false for the workstation. Emit
`group:add:mediauser:media` if and only if `in_media_group` is false for
the workstation. If both are true, emit neither. If both are false, emit
both in the order `debug` then `media`.

The exact action strings are `group:add:mediauser:debug` and
`group:add:mediauser:media`. The prefix `group:add:` is fixed and the
username is `mediauser`. Do not substitute `debug` for `debugger` or
`media` for `mediagroup`; the group names are load-bearing.

The ordering rule matters because the compliance runbook applies group
memberships in the order emitted, and `debug` before `media` matches the
order in which the two groups were originally provisioned on the golden
workstation image. Reversing the order will not cause the compliance
scanner to reject the plan today, but the ordering is part of the
documented convention and Section 10 relies on it.

There is a scoped non-goal. The lab does not remove `mediauser` from any
group. The plan never emits a `group:del:` action. If a workstation has
`mediauser` in an unexpected group (for example `wheel`, which the audit
found on ws-004), the compliance scanner logs a warning but the
remediation plan does not act on it. Removing unexpected group
memberships is the subject of a separate follow-up ticket and is out of
scope for this postmortem.

## Section 8 -- ulimit for RLIMIT_CORE

The `RLIMIT_CORE` limit controls the maximum size of a core dump that a
process may produce. The value is stored per-process, initialized from
the shell's `ulimit -c` and PAM's `limits.conf`. The lab charter
requires that both the soft and hard limits be set to `unlimited` on
every diagnostic workstation so that the media pipeline can produce
full-size core dumps.

The inventory records the effective `RLIMIT_CORE` soft and hard limits
for the `mediauser` account under the keys `core_soft` and `core_hard`.
The value is either the literal string `unlimited` or a numeric string
in kilobytes.

The remediation is: emit the action `ulimit:core:unlimited` if and only
if either the soft limit or the hard limit is not the literal string
`unlimited`. Both must be `unlimited` for the workstation to skip the
action. A value of `0` triggers the action; so does `4096`; so does any
other numeric value.

The exact action string is `ulimit:core:unlimited`. The prefix
`ulimit:core:` is fixed and the value is the literal string
`unlimited`. Do not substitute `infinity`, do not use `-1`, do not use
an absurdly large numeric value like `18446744073709551615`.

The action's position in the plan is fifth when present, after the group
memberships and before the filesystem-permission action. The reason is
that raising the ulimit is a low-risk change that takes effect on the
next `mediauser` login, and completing it before the filesystem
adjustments minimises the chance of a partial state where the scratch
directory is writable but the produced cores are truncated.

## Section 9 -- filesystem permissions on the scratch directory and fixtures

The `/var/lib/media/scratch` directory is the working directory for
diagnostic reproducers. The lab charter requires that it be owned by
`mediauser:media` with the octal mode `2770`. The setgid bit ensures
that files created inside the directory inherit the `media` group, which
is required so that other members of the on-call rotation can read
coredumps left behind by a reproducer. Any deviation -- wrong owner,
wrong group, missing setgid, wrong access bits -- must be corrected.

The inventory records the current mode, owner, and group of the scratch
directory for each workstation under the keys `scratch_perms`,
`scratch_owner`, and `scratch_group`.

The remediation is: emit the action
`perms:/var/lib/media/scratch:2770:mediauser:media` if and only if any
of the three fields differs from the required value. If all three match
(`2770`, `mediauser`, `media`) do not emit the action.

The exact action string is
`perms:/var/lib/media/scratch:2770:mediauser:media`. The prefix
`perms:` is fixed, the path is absolute, the mode is a four-digit
octal literal, and the owner/group pair is a colon-separated pair. Do
not use `chmod`, `chown`, or `chgrp` prefixes; the compliance runbook
parses the `perms:` prefix directly.

There is a second filesystem concern. If the workstation has the
immutable attribute `+i` set on `/var/lib/media/scratch`, no
permission or ownership change will succeed until the attribute is
cleared. The remediation for that state is a separate action:
`fsattr:-i:/var/lib/media/scratch`, emitted if and only if
`scratch_immutable` is true for the workstation. When both the
permission action and the immutable clearance are needed, the
permission action is emitted first even though the runbook applies the
immutable clearance first; the plan orders by remediation family, not
application family, and Section 10 documents the emission order.

The final action in every plan is a fixture-permissions normalization.
Every workstation runs one of three fixture workloads (`tiff`, `png`,
`mp4`) and the fixture file at `/app/fixtures/<workload>/sample.<workload>`
must be readable by the `mediauser` account with mode `0644`. The lab
charter requires this normalization even for workstations that are
otherwise fully compliant, so the fixture-permissions action is emitted
for every workstation regardless of the current state of the fixture.

The exact action strings are
`fixture-perms:/app/fixtures/tiff/sample.tiff:0644`,
`fixture-perms:/app/fixtures/png/sample.png:0644`, and
`fixture-perms:/app/fixtures/mp4/sample.mp4:0644`, one per workstation
matching the workstation's assigned workload. The prefix
`fixture-perms:` is fixed, the path is absolute, and the mode is a
four-digit octal literal `0644` with the leading zero.

## Section 10 -- Canonical decision matrix

The canonical ordering for the emit sequence is:

1. `sysctl:kernel.yama.ptrace_scope=0` -- when `ptrace_scope != 0`.
2. `sysctl:kernel.core_pattern=core` -- when `core_pattern != "core"`.
3. `sysctl:fs.suid_dumpable=2` -- when `suid_dumpable != 2`.
4. `systemd:/etc/systemd/coredump.conf.d/media.conf` -- when the
   drop-in file is absent (`coredump_conf == false`).
5. `group:add:mediauser:debug` -- when `in_debug_group == false`.
6. `group:add:mediauser:media` -- when `in_media_group == false`.
7. `ulimit:core:unlimited` -- when either `core_soft != "unlimited"`
   or `core_hard != "unlimited"`.
8. `perms:/var/lib/media/scratch:2770:mediauser:media` -- when any of
   `scratch_perms`, `scratch_owner`, `scratch_group` differs from
   `2770`, `mediauser`, `media`.
9. `fsattr:-i:/var/lib/media/scratch` -- when
   `scratch_immutable == true`.
10. `fixture-perms:/app/fixtures/<workload>/sample.<workload>:0644` --
    always emitted, keyed off the workstation's assigned workload.

The ordering is by family, not by application phase. The permission
action (step 8) is emitted before the immutable clearance (step 9) even
though the immutable clearance is applied first at runtime; the plan is
a declarative order for downstream review, not an imperative order for
the runbook. When applying the plan, the runbook operator is expected
to reorder steps 8 and 9 into their operational order (clear the
immutable attribute, then reset the permission) but the plan itself
must be emitted in the order given above.

Every workstation emits at least one action -- the fixture-permissions
normalization from step 10 -- even if it is fully compliant on steps 1
through 9. An empty plan for a workstation in the inventory is always
incorrect.

## Section 11 -- Operational review and out-of-scope items

The following items were considered and explicitly rejected as out of
scope for this postmortem:

Rotating the `mediauser` password is a security hygiene task tracked in
a separate ticket. The Rego library must not emit any credential-
related action.

Reprovisioning the `debug` and `media` groups from scratch is out of
scope. The Rego library must not emit any `group:del:` or
`group:reprovision:` action.

Auditing the media pipeline for memory-safety bugs is a separate,
ongoing engineering effort. The Rego library must not emit any action
that references the pipeline source code, the pipeline binaries, or
any file under `/opt/media-pipeline`.

Enabling ptrace across user boundaries (Yama level 0 across UIDs) is
what this postmortem authorises; enabling it across the network via
kexec or kdb is not. The Rego library must not emit any kexec, kdb,
or remote-debug related action.

Any sysctl not enumerated in Sections 3, 4, or 5 is out of scope.
Specifically, the following sysctls are frequent false-positive
triggers on hardening scanners and MUST NOT appear in the plan:
`kernel.perf_event_paranoid`, `kernel.kptr_restrict`,
`kernel.unprivileged_userns_clone`, `kernel.core_uses_pid`,
`kernel.dmesg_restrict`, `kernel.randomize_va_space`.

Any systemd unit override not at
`/etc/systemd/coredump.conf.d/media.conf` is out of scope.
Specifically, no override may be emitted for `journald.conf`,
`system.conf`, `logind.conf`, or any drop-in under
`/etc/systemd/system.conf.d/`.

Any group other than `debug` and `media` is out of scope. The
`mediauser` account may be a member of additional groups on some
workstations; the plan neither confirms nor removes those memberships.

The ulimit action is scoped to `RLIMIT_CORE`. No other rlimit is
managed by this plan. `RLIMIT_NOFILE`, `RLIMIT_STACK`, `RLIMIT_AS`,
and `RLIMIT_MEMLOCK` are the subject of a separate follow-up.

The filesystem-permission action is scoped to
`/var/lib/media/scratch` for the directory itself. No recursive
permission change is emitted; per-file permission drift inside the
scratch directory is handled by a nightly cronjob outside this
plan.

The fixture-permissions action is scoped to the single sample file
matching the workstation's assigned workload. No other file under
`/app/fixtures/` is managed by this plan; the additional fixture
files that ship with the diagnostic image are read-only reference
material and their permissions are managed at build time.

The decision matrix is complete. Any deviation observed on the
workstation that is not listed in Sections 3 through 9 is out of scope
for this plan and is either not a compliance concern or is tracked in a
separate ticket.

---

The remainder of this file is an annotated verbatim archive of the
individual per-workstation triage notes captured during the sweep. The
Rego library does not need to read the archive to derive the correct
plan; every rule required to reproduce the golden plans is stated in
Sections 3 through 10 above. The archive is provided for auditability.

## Per-workstation triage archive

The following ten sub-sections are the annotated verbatim triage notes for each workstation in the sweep. The notes are ordered by workstation identifier and each records the sweep-day observation for each family of the decision matrix, the reason the workstation ended up in its observed state (drawn from the November 2025 refresh changelog in Appendix A), and the resulting per-workstation plan. The plans stated here are the exact contents of the golden plan JSON files committed to `/app/golden/`; a Rego library that reproduces the golden output for the ten workstations documented below is a passing submission.

### WS-001 -- render-a01 (intel, kernel 6.6.32, tiff workload)
The sweep of ws-001 was completed by Sanchez on 2026-02-11 at 09:42 UTC. The workstation is a intel host running the 6.6.32 downstream kernel and is currently assigned the TIFF fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-001 was observed at level 3. That level disables ptrace entirely and requires a reboot to relax and matches the November 2025 refresh default. The remediation plan for ws-001 therefore emits the action `sysctl:kernel.yama.ptrace_scope=0`. Sanchez verified during the sweep that the value was persisted in `/etc/sysctl.d/50-yama.conf` so that the sysctl write will survive a reboot once the file is regenerated by the remediation runbook.
The kernel.core_pattern on ws-001 was observed as `|/bin/false`. This value discards the core file instead of writing it to the working directory, which prevents post-mortem inspection by gdb. The remediation plan for ws-001 therefore emits `sysctl:kernel.core_pattern=core`. Sanchez noted that the value was set by a stale copy of `/etc/sysctl.d/99-refresh.conf` and that the remediation runbook removes that file as part of applying the sysctl write.
The fs.suid_dumpable value on ws-001 was already 2, which is the lab-required setting that permits core dumps for the set-user-id GPU shim owned by root but readable by the debug group. Sanchez did not raise any action for this family.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was absent on ws-001. Without the drop-in, `ProcessSizeMax` defaults to 2 GiB minus the host page-cache overhead and `MaxUse` defaults to 10 percent of the device holding `/var/lib/systemd/coredump`, both of which are too low for the media pipeline's typical core dump. The remediation plan for ws-001 therefore emits `systemd:/etc/systemd/coredump.conf.d/media.conf`. The runbook will create the file with the lab-approved content and issue a `systemctl daemon-reload`.
On ws-001, the `mediauser` account was NOT a member of the `debug` group. Without membership, the on-call engineer cannot read files in `/var/lib/systemd/coredump/` even after `fs.suid_dumpable` is set to 2, which defeats the purpose of the sysctl remediation. The plan for ws-001 therefore emits `group:add:mediauser:debug`.
On ws-001, the `mediauser` account was already a member of the `media` group. Sanchez confirmed this via `id mediauser` and by touching a test file inside `/var/lib/media/scratch`, which inherited the `media` group as expected. No media-group action is emitted.
The `mediauser` RLIMIT_CORE values on ws-001 were observed as soft=`0` and hard=`0`. Either value being anything other than `unlimited` will truncate a diagnostic core dump for a large TIFF or MP4 reproducer, so the plan for ws-001 emits `ulimit:core:unlimited`. The remediation runbook updates the lab drop-in at `/etc/security/limits.d/50-media.conf` to enforce the new limits at next login.
The `/var/lib/media/scratch` directory on ws-001 was observed at mode `0770` owned by `root:media`. The lab-required posture is mode 2770 owned by mediauser:media, so the plan emits `perms:/var/lib/media/scratch:2770:mediauser:media`. The setgid bit is load-bearing: without it, files created inside the directory do not inherit the `media` group and become unreadable by the on-call rotation.
No immutable attribute was set on `/var/lib/media/scratch` on ws-001. Sanchez confirmed with `lsattr -d /var/lib/media/scratch`. No fsattr action is emitted.
Finally, ws-001 is running the TIFF fixture workload, so the plan emits `fixture-perms:/app/fixtures/tiff/sample.tiff:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-001 therefore contains 7 action(s), in the following order:

1. `sysctl:kernel.yama.ptrace_scope=0`
2. `sysctl:kernel.core_pattern=core`
3. `systemd:/etc/systemd/coredump.conf.d/media.conf`
4. `group:add:mediauser:debug`
5. `ulimit:core:unlimited`
6. `perms:/var/lib/media/scratch:2770:mediauser:media`
7. `fixture-perms:/app/fixtures/tiff/sample.tiff:0644`

The golden plan file for ws-001 is committed at `/app/golden/plan_ws001.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-001.


### WS-002 -- render-a02 (intel, kernel 6.6.32, png workload)
The sweep of ws-002 was completed by Okoro on 2026-02-11 at 10:15 UTC. The workstation is a intel host running the 6.6.32 downstream kernel and is currently assigned the PNG fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-002 was observed at level 1. That level restricts ptrace to parent processes and matches the November 2025 refresh default. The remediation plan for ws-002 therefore emits the action `sysctl:kernel.yama.ptrace_scope=0`. Okoro verified during the sweep that the value was persisted in `/etc/sysctl.d/50-yama.conf` so that the sysctl write will survive a reboot once the file is regenerated by the remediation runbook.
The kernel.core_pattern on ws-002 was observed as `|/bin/false`. This value discards the core file instead of writing it to the working directory, which prevents post-mortem inspection by gdb. The remediation plan for ws-002 therefore emits `sysctl:kernel.core_pattern=core`. Okoro noted that the value was set by a stale copy of `/etc/sysctl.d/99-refresh.conf` and that the remediation runbook removes that file as part of applying the sysctl write.
The fs.suid_dumpable value on ws-002 was already 2, which is the lab-required setting that permits core dumps for the set-user-id GPU shim owned by root but readable by the debug group. Okoro did not raise any action for this family.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was absent on ws-002. Without the drop-in, `ProcessSizeMax` defaults to 2 GiB minus the host page-cache overhead and `MaxUse` defaults to 10 percent of the device holding `/var/lib/systemd/coredump`, both of which are too low for the media pipeline's typical core dump. The remediation plan for ws-002 therefore emits `systemd:/etc/systemd/coredump.conf.d/media.conf`. The runbook will create the file with the lab-approved content and issue a `systemctl daemon-reload`.
On ws-002, the `mediauser` account was already a member of the `debug` group. Okoro confirmed this by reading `/etc/group` and by running `id mediauser`. No debug-group action is emitted.
On ws-002, the `mediauser` account was already a member of the `media` group. Okoro confirmed this via `id mediauser` and by touching a test file inside `/var/lib/media/scratch`, which inherited the `media` group as expected. No media-group action is emitted.
The `mediauser` RLIMIT_CORE values on ws-002 were observed as soft=`0` and hard=`0`. Either value being anything other than `unlimited` will truncate a diagnostic core dump for a large TIFF or MP4 reproducer, so the plan for ws-002 emits `ulimit:core:unlimited`. The remediation runbook updates the lab drop-in at `/etc/security/limits.d/50-media.conf` to enforce the new limits at next login.
The `/var/lib/media/scratch` directory on ws-002 was already at mode 2770 owned by mediauser:media. Okoro verified with `stat -c '%a %U %G' /var/lib/media/scratch`. No permission action is emitted.
No immutable attribute was set on `/var/lib/media/scratch` on ws-002. Okoro confirmed with `lsattr -d /var/lib/media/scratch`. No fsattr action is emitted.
Finally, ws-002 is running the PNG fixture workload, so the plan emits `fixture-perms:/app/fixtures/png/sample.png:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-002 therefore contains 5 action(s), in the following order:

1. `sysctl:kernel.yama.ptrace_scope=0`
2. `sysctl:kernel.core_pattern=core`
3. `systemd:/etc/systemd/coredump.conf.d/media.conf`
4. `ulimit:core:unlimited`
5. `fixture-perms:/app/fixtures/png/sample.png:0644`

The golden plan file for ws-002 is committed at `/app/golden/plan_ws002.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-002.


### WS-003 -- render-a03 (intel, kernel 6.6.32, mp4 workload)
The sweep of ws-003 was completed by Palmieri on 2026-02-11 at 11:03 UTC. The workstation is a intel host running the 6.6.32 downstream kernel and is currently assigned the MP4 fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-003 was already at level 0, so the workstation does not need the ptrace_scope remediation. Palmieri confirmed the value by reading `/proc/sys/kernel/yama/ptrace_scope` twice with an intervening process spawn to make sure the value was not being reset by a stale sysctl.d file. No action is emitted for this family.
The kernel.core_pattern on ws-003 was already set to the literal string `core`. Palmieri confirmed the value by tailing `/proc/sys/kernel/core_pattern` and by triggering a synthetic crash via `sh -c 'kill -SEGV $$'`, which produced a file named `core` in the working directory as expected. No sysctl action is needed for the core_pattern family.
The fs.suid_dumpable value on ws-003 was observed at 1, which produces root-owned mode-0600 cores that the debug group cannot read and is incompatible with the lab charter. The remediation plan for ws-003 therefore emits `sysctl:fs.suid_dumpable=2`. Palmieri recorded the current value from `/proc/sys/fs/suid_dumpable` at 08:41 UTC and observed no drift during the sweep window.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was present on ws-003 at sweep time. Palmieri did not open the file (the sweep scripts intentionally do not read the drop-in content because the compliance scanner treats presence as sufficient) and did not emit the systemd drop-in action.
On ws-003, the `mediauser` account was already a member of the `debug` group. Palmieri confirmed this by reading `/etc/group` and by running `id mediauser`. No debug-group action is emitted.
On ws-003, the `mediauser` account was already a member of the `media` group. Palmieri confirmed this via `id mediauser` and by touching a test file inside `/var/lib/media/scratch`, which inherited the `media` group as expected. No media-group action is emitted.
The `mediauser` RLIMIT_CORE soft and hard values on ws-003 were both `unlimited` at sweep time. Palmieri confirmed this by switching to the `mediauser` shell and running `ulimit -c` and `ulimit -Hc`. No ulimit action is emitted.
The `/var/lib/media/scratch` directory on ws-003 was already at mode 2770 owned by mediauser:media. Palmieri verified with `stat -c '%a %U %G' /var/lib/media/scratch`. No permission action is emitted.
No immutable attribute was set on `/var/lib/media/scratch` on ws-003. Palmieri confirmed with `lsattr -d /var/lib/media/scratch`. No fsattr action is emitted.
Finally, ws-003 is running the MP4 fixture workload, so the plan emits `fixture-perms:/app/fixtures/mp4/sample.mp4:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-003 therefore contains 2 action(s), in the following order:

1. `sysctl:fs.suid_dumpable=2`
2. `fixture-perms:/app/fixtures/mp4/sample.mp4:0644`

The golden plan file for ws-003 is committed at `/app/golden/plan_ws003.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-003.


### WS-004 -- render-b01 (amd, kernel 6.6.31, tiff workload)
The sweep of ws-004 was completed by Yoshida on 2026-02-11 at 11:41 UTC. The workstation is a amd host running the 6.6.31 downstream kernel and is currently assigned the TIFF fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-004 was observed at level 3. That level disables ptrace entirely and requires a reboot to relax and matches the November 2025 refresh default. The remediation plan for ws-004 therefore emits the action `sysctl:kernel.yama.ptrace_scope=0`. Yoshida verified during the sweep that the value was persisted in `/etc/sysctl.d/50-yama.conf` so that the sysctl write will survive a reboot once the file is regenerated by the remediation runbook.
The kernel.core_pattern on ws-004 was already set to the literal string `core`. Yoshida confirmed the value by tailing `/proc/sys/kernel/core_pattern` and by triggering a synthetic crash via `sh -c 'kill -SEGV $$'`, which produced a file named `core` in the working directory as expected. No sysctl action is needed for the core_pattern family.
The fs.suid_dumpable value on ws-004 was already 2, which is the lab-required setting that permits core dumps for the set-user-id GPU shim owned by root but readable by the debug group. Yoshida did not raise any action for this family.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was absent on ws-004. Without the drop-in, `ProcessSizeMax` defaults to 2 GiB minus the host page-cache overhead and `MaxUse` defaults to 10 percent of the device holding `/var/lib/systemd/coredump`, both of which are too low for the media pipeline's typical core dump. The remediation plan for ws-004 therefore emits `systemd:/etc/systemd/coredump.conf.d/media.conf`. The runbook will create the file with the lab-approved content and issue a `systemctl daemon-reload`.
On ws-004, the `mediauser` account was NOT a member of the `debug` group. Without membership, the on-call engineer cannot read files in `/var/lib/systemd/coredump/` even after `fs.suid_dumpable` is set to 2, which defeats the purpose of the sysctl remediation. The plan for ws-004 therefore emits `group:add:mediauser:debug`.
On ws-004, the `mediauser` account was NOT a member of the `media` group. Without that membership the on-call engineer cannot write to `/var/lib/media/scratch`, which is where the reproducer runs. The plan for ws-004 therefore emits `group:add:mediauser:media`. This action is emitted after the `debug` group action if both are needed, per the ordering documented in Section 7 of the postmortem body.
The `mediauser` RLIMIT_CORE values on ws-004 were observed as soft=`0` and hard=`0`. Either value being anything other than `unlimited` will truncate a diagnostic core dump for a large TIFF or MP4 reproducer, so the plan for ws-004 emits `ulimit:core:unlimited`. The remediation runbook updates the lab drop-in at `/etc/security/limits.d/50-media.conf` to enforce the new limits at next login.
The `/var/lib/media/scratch` directory on ws-004 was observed at mode `0755` owned by `root:root`. The lab-required posture is mode 2770 owned by mediauser:media, so the plan emits `perms:/var/lib/media/scratch:2770:mediauser:media`. The setgid bit is load-bearing: without it, files created inside the directory do not inherit the `media` group and become unreadable by the on-call rotation.
No immutable attribute was set on `/var/lib/media/scratch` on ws-004. Yoshida confirmed with `lsattr -d /var/lib/media/scratch`. No fsattr action is emitted.
Finally, ws-004 is running the TIFF fixture workload, so the plan emits `fixture-perms:/app/fixtures/tiff/sample.tiff:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-004 therefore contains 7 action(s), in the following order:

1. `sysctl:kernel.yama.ptrace_scope=0`
2. `systemd:/etc/systemd/coredump.conf.d/media.conf`
3. `group:add:mediauser:debug`
4. `group:add:mediauser:media`
5. `ulimit:core:unlimited`
6. `perms:/var/lib/media/scratch:2770:mediauser:media`
7. `fixture-perms:/app/fixtures/tiff/sample.tiff:0644`

The golden plan file for ws-004 is committed at `/app/golden/plan_ws004.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-004.


### WS-005 -- render-b02 (amd, kernel 6.6.31, png workload)
The sweep of ws-005 was completed by Bergstrom on 2026-02-11 at 12:22 UTC. The workstation is a amd host running the 6.6.31 downstream kernel and is currently assigned the PNG fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-005 was observed at level 1. That level restricts ptrace to parent processes and matches the November 2025 refresh default. The remediation plan for ws-005 therefore emits the action `sysctl:kernel.yama.ptrace_scope=0`. Bergstrom verified during the sweep that the value was persisted in `/etc/sysctl.d/50-yama.conf` so that the sysctl write will survive a reboot once the file is regenerated by the remediation runbook.
The kernel.core_pattern on ws-005 was observed as `|/bin/false`. This value discards the core file instead of writing it to the working directory, which prevents post-mortem inspection by gdb. The remediation plan for ws-005 therefore emits `sysctl:kernel.core_pattern=core`. Bergstrom noted that the value was set by a stale copy of `/etc/sysctl.d/99-refresh.conf` and that the remediation runbook removes that file as part of applying the sysctl write.
The fs.suid_dumpable value on ws-005 was already 2, which is the lab-required setting that permits core dumps for the set-user-id GPU shim owned by root but readable by the debug group. Bergstrom did not raise any action for this family.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was present on ws-005 at sweep time. Bergstrom did not open the file (the sweep scripts intentionally do not read the drop-in content because the compliance scanner treats presence as sufficient) and did not emit the systemd drop-in action.
On ws-005, the `mediauser` account was already a member of the `debug` group. Bergstrom confirmed this by reading `/etc/group` and by running `id mediauser`. No debug-group action is emitted.
On ws-005, the `mediauser` account was already a member of the `media` group. Bergstrom confirmed this via `id mediauser` and by touching a test file inside `/var/lib/media/scratch`, which inherited the `media` group as expected. No media-group action is emitted.
The `mediauser` RLIMIT_CORE values on ws-005 were observed as soft=`0` and hard=`0`. Either value being anything other than `unlimited` will truncate a diagnostic core dump for a large TIFF or MP4 reproducer, so the plan for ws-005 emits `ulimit:core:unlimited`. The remediation runbook updates the lab drop-in at `/etc/security/limits.d/50-media.conf` to enforce the new limits at next login.
The `/var/lib/media/scratch` directory on ws-005 was already at mode 2770 owned by mediauser:media. Bergstrom verified with `stat -c '%a %U %G' /var/lib/media/scratch`. No permission action is emitted.
No immutable attribute was set on `/var/lib/media/scratch` on ws-005. Bergstrom confirmed with `lsattr -d /var/lib/media/scratch`. No fsattr action is emitted.
Finally, ws-005 is running the PNG fixture workload, so the plan emits `fixture-perms:/app/fixtures/png/sample.png:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-005 therefore contains 4 action(s), in the following order:

1. `sysctl:kernel.yama.ptrace_scope=0`
2. `sysctl:kernel.core_pattern=core`
3. `ulimit:core:unlimited`
4. `fixture-perms:/app/fixtures/png/sample.png:0644`

The golden plan file for ws-005 is committed at `/app/golden/plan_ws005.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-005.


### WS-006 -- render-b03 (amd, kernel 6.6.31, mp4 workload)
The sweep of ws-006 was completed by Hakim on 2026-02-11 at 13:07 UTC. The workstation is a amd host running the 6.6.31 downstream kernel and is currently assigned the MP4 fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-006 was observed at level 2. That level refuses ptrace attach from any non-root user and matches the November 2025 refresh default. The remediation plan for ws-006 therefore emits the action `sysctl:kernel.yama.ptrace_scope=0`. Hakim verified during the sweep that the value was persisted in `/etc/sysctl.d/50-yama.conf` so that the sysctl write will survive a reboot once the file is regenerated by the remediation runbook.
The kernel.core_pattern on ws-006 was already set to the literal string `core`. Hakim confirmed the value by tailing `/proc/sys/kernel/core_pattern` and by triggering a synthetic crash via `sh -c 'kill -SEGV $$'`, which produced a file named `core` in the working directory as expected. No sysctl action is needed for the core_pattern family.
The fs.suid_dumpable value on ws-006 was observed at 0, which disables suid core dumps entirely and is incompatible with the lab charter. The remediation plan for ws-006 therefore emits `sysctl:fs.suid_dumpable=2`. Hakim recorded the current value from `/proc/sys/fs/suid_dumpable` at 08:41 UTC and observed no drift during the sweep window.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was absent on ws-006. Without the drop-in, `ProcessSizeMax` defaults to 2 GiB minus the host page-cache overhead and `MaxUse` defaults to 10 percent of the device holding `/var/lib/systemd/coredump`, both of which are too low for the media pipeline's typical core dump. The remediation plan for ws-006 therefore emits `systemd:/etc/systemd/coredump.conf.d/media.conf`. The runbook will create the file with the lab-approved content and issue a `systemctl daemon-reload`.
On ws-006, the `mediauser` account was already a member of the `debug` group. Hakim confirmed this by reading `/etc/group` and by running `id mediauser`. No debug-group action is emitted.
On ws-006, the `mediauser` account was already a member of the `media` group. Hakim confirmed this via `id mediauser` and by touching a test file inside `/var/lib/media/scratch`, which inherited the `media` group as expected. No media-group action is emitted.
The `mediauser` RLIMIT_CORE soft and hard values on ws-006 were both `unlimited` at sweep time. Hakim confirmed this by switching to the `mediauser` shell and running `ulimit -c` and `ulimit -Hc`. No ulimit action is emitted.
The `/var/lib/media/scratch` directory on ws-006 was observed at mode `0777` owned by `mediauser:media`. The lab-required posture is mode 2770 owned by mediauser:media, so the plan emits `perms:/var/lib/media/scratch:2770:mediauser:media`. The setgid bit is load-bearing: without it, files created inside the directory do not inherit the `media` group and become unreadable by the on-call rotation.
On ws-006, the `/var/lib/media/scratch` directory carried the immutable attribute `+i`, which was applied by a since-reverted attempt to prevent tampering during the November refresh. The attribute prevents any permission or ownership change from succeeding, so the plan for ws-006 emits `fsattr:-i:/var/lib/media/scratch`. The runbook applies the immutable clearance before the permission change, even though the emission order lists the permission action first.
Finally, ws-006 is running the MP4 fixture workload, so the plan emits `fixture-perms:/app/fixtures/mp4/sample.mp4:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-006 therefore contains 6 action(s), in the following order:

1. `sysctl:kernel.yama.ptrace_scope=0`
2. `sysctl:fs.suid_dumpable=2`
3. `systemd:/etc/systemd/coredump.conf.d/media.conf`
4. `perms:/var/lib/media/scratch:2770:mediauser:media`
5. `fsattr:-i:/var/lib/media/scratch`
6. `fixture-perms:/app/fixtures/mp4/sample.mp4:0644`

The golden plan file for ws-006 is committed at `/app/golden/plan_ws006.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-006.


### WS-007 -- render-c01 (apple-silicon, kernel 6.7.4, tiff workload)
The sweep of ws-007 was completed by Vasquez on 2026-02-11 at 13:49 UTC. The workstation is a apple-silicon host running the 6.7.4 downstream kernel and is currently assigned the TIFF fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-007 was observed at level 3. That level disables ptrace entirely and requires a reboot to relax and matches the November 2025 refresh default. The remediation plan for ws-007 therefore emits the action `sysctl:kernel.yama.ptrace_scope=0`. Vasquez verified during the sweep that the value was persisted in `/etc/sysctl.d/50-yama.conf` so that the sysctl write will survive a reboot once the file is regenerated by the remediation runbook.
The kernel.core_pattern on ws-007 was observed as `|/bin/false`. This value discards the core file instead of writing it to the working directory, which prevents post-mortem inspection by gdb. The remediation plan for ws-007 therefore emits `sysctl:kernel.core_pattern=core`. Vasquez noted that the value was set by a stale copy of `/etc/sysctl.d/99-refresh.conf` and that the remediation runbook removes that file as part of applying the sysctl write.
The fs.suid_dumpable value on ws-007 was already 2, which is the lab-required setting that permits core dumps for the set-user-id GPU shim owned by root but readable by the debug group. Vasquez did not raise any action for this family.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was absent on ws-007. Without the drop-in, `ProcessSizeMax` defaults to 2 GiB minus the host page-cache overhead and `MaxUse` defaults to 10 percent of the device holding `/var/lib/systemd/coredump`, both of which are too low for the media pipeline's typical core dump. The remediation plan for ws-007 therefore emits `systemd:/etc/systemd/coredump.conf.d/media.conf`. The runbook will create the file with the lab-approved content and issue a `systemctl daemon-reload`.
On ws-007, the `mediauser` account was NOT a member of the `debug` group. Without membership, the on-call engineer cannot read files in `/var/lib/systemd/coredump/` even after `fs.suid_dumpable` is set to 2, which defeats the purpose of the sysctl remediation. The plan for ws-007 therefore emits `group:add:mediauser:debug`.
On ws-007, the `mediauser` account was already a member of the `media` group. Vasquez confirmed this via `id mediauser` and by touching a test file inside `/var/lib/media/scratch`, which inherited the `media` group as expected. No media-group action is emitted.
The `mediauser` RLIMIT_CORE values on ws-007 were observed as soft=`0` and hard=`0`. Either value being anything other than `unlimited` will truncate a diagnostic core dump for a large TIFF or MP4 reproducer, so the plan for ws-007 emits `ulimit:core:unlimited`. The remediation runbook updates the lab drop-in at `/etc/security/limits.d/50-media.conf` to enforce the new limits at next login.
The `/var/lib/media/scratch` directory on ws-007 was observed at mode `0770` owned by `mediauser:media`. The lab-required posture is mode 2770 owned by mediauser:media, so the plan emits `perms:/var/lib/media/scratch:2770:mediauser:media`. The setgid bit is load-bearing: without it, files created inside the directory do not inherit the `media` group and become unreadable by the on-call rotation.
No immutable attribute was set on `/var/lib/media/scratch` on ws-007. Vasquez confirmed with `lsattr -d /var/lib/media/scratch`. No fsattr action is emitted.
Finally, ws-007 is running the TIFF fixture workload, so the plan emits `fixture-perms:/app/fixtures/tiff/sample.tiff:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-007 therefore contains 7 action(s), in the following order:

1. `sysctl:kernel.yama.ptrace_scope=0`
2. `sysctl:kernel.core_pattern=core`
3. `systemd:/etc/systemd/coredump.conf.d/media.conf`
4. `group:add:mediauser:debug`
5. `ulimit:core:unlimited`
6. `perms:/var/lib/media/scratch:2770:mediauser:media`
7. `fixture-perms:/app/fixtures/tiff/sample.tiff:0644`

The golden plan file for ws-007 is committed at `/app/golden/plan_ws007.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-007.


### WS-008 -- render-c02 (apple-silicon, kernel 6.7.4, png workload)
The sweep of ws-008 was completed by Nishimura on 2026-02-11 at 14:24 UTC. The workstation is a apple-silicon host running the 6.7.4 downstream kernel and is currently assigned the PNG fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-008 was observed at level 3. That level disables ptrace entirely and requires a reboot to relax and matches the November 2025 refresh default. The remediation plan for ws-008 therefore emits the action `sysctl:kernel.yama.ptrace_scope=0`. Nishimura verified during the sweep that the value was persisted in `/etc/sysctl.d/50-yama.conf` so that the sysctl write will survive a reboot once the file is regenerated by the remediation runbook.
The kernel.core_pattern on ws-008 was already set to the literal string `core`. Nishimura confirmed the value by tailing `/proc/sys/kernel/core_pattern` and by triggering a synthetic crash via `sh -c 'kill -SEGV $$'`, which produced a file named `core` in the working directory as expected. No sysctl action is needed for the core_pattern family.
The fs.suid_dumpable value on ws-008 was already 2, which is the lab-required setting that permits core dumps for the set-user-id GPU shim owned by root but readable by the debug group. Nishimura did not raise any action for this family.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was absent on ws-008. Without the drop-in, `ProcessSizeMax` defaults to 2 GiB minus the host page-cache overhead and `MaxUse` defaults to 10 percent of the device holding `/var/lib/systemd/coredump`, both of which are too low for the media pipeline's typical core dump. The remediation plan for ws-008 therefore emits `systemd:/etc/systemd/coredump.conf.d/media.conf`. The runbook will create the file with the lab-approved content and issue a `systemctl daemon-reload`.
On ws-008, the `mediauser` account was already a member of the `debug` group. Nishimura confirmed this by reading `/etc/group` and by running `id mediauser`. No debug-group action is emitted.
On ws-008, the `mediauser` account was NOT a member of the `media` group. Without that membership the on-call engineer cannot write to `/var/lib/media/scratch`, which is where the reproducer runs. The plan for ws-008 therefore emits `group:add:mediauser:media`. This action is emitted after the `debug` group action if both are needed, per the ordering documented in Section 7 of the postmortem body.
The `mediauser` RLIMIT_CORE values on ws-008 were observed as soft=`0` and hard=`0`. Either value being anything other than `unlimited` will truncate a diagnostic core dump for a large TIFF or MP4 reproducer, so the plan for ws-008 emits `ulimit:core:unlimited`. The remediation runbook updates the lab drop-in at `/etc/security/limits.d/50-media.conf` to enforce the new limits at next login.
The `/var/lib/media/scratch` directory on ws-008 was already at mode 2770 owned by mediauser:media. Nishimura verified with `stat -c '%a %U %G' /var/lib/media/scratch`. No permission action is emitted.
No immutable attribute was set on `/var/lib/media/scratch` on ws-008. Nishimura confirmed with `lsattr -d /var/lib/media/scratch`. No fsattr action is emitted.
Finally, ws-008 is running the PNG fixture workload, so the plan emits `fixture-perms:/app/fixtures/png/sample.png:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-008 therefore contains 5 action(s), in the following order:

1. `sysctl:kernel.yama.ptrace_scope=0`
2. `systemd:/etc/systemd/coredump.conf.d/media.conf`
3. `group:add:mediauser:media`
4. `ulimit:core:unlimited`
5. `fixture-perms:/app/fixtures/png/sample.png:0644`

The golden plan file for ws-008 is committed at `/app/golden/plan_ws008.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-008.


### WS-009 -- render-c03 (apple-silicon, kernel 6.7.4, mp4 workload)
The sweep of ws-009 was completed by Delacroix on 2026-02-11 at 15:03 UTC. The workstation is a apple-silicon host running the 6.7.4 downstream kernel and is currently assigned the MP4 fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-009 was already at level 0, so the workstation does not need the ptrace_scope remediation. Delacroix confirmed the value by reading `/proc/sys/kernel/yama/ptrace_scope` twice with an intervening process spawn to make sure the value was not being reset by a stale sysctl.d file. No action is emitted for this family.
The kernel.core_pattern on ws-009 was observed as `|/bin/false`. This value discards the core file instead of writing it to the working directory, which prevents post-mortem inspection by gdb. The remediation plan for ws-009 therefore emits `sysctl:kernel.core_pattern=core`. Delacroix noted that the value was set by a stale copy of `/etc/sysctl.d/99-refresh.conf` and that the remediation runbook removes that file as part of applying the sysctl write.
The fs.suid_dumpable value on ws-009 was observed at 0, which disables suid core dumps entirely and is incompatible with the lab charter. The remediation plan for ws-009 therefore emits `sysctl:fs.suid_dumpable=2`. Delacroix recorded the current value from `/proc/sys/fs/suid_dumpable` at 08:41 UTC and observed no drift during the sweep window.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was present on ws-009 at sweep time. Delacroix did not open the file (the sweep scripts intentionally do not read the drop-in content because the compliance scanner treats presence as sufficient) and did not emit the systemd drop-in action.
On ws-009, the `mediauser` account was already a member of the `debug` group. Delacroix confirmed this by reading `/etc/group` and by running `id mediauser`. No debug-group action is emitted.
On ws-009, the `mediauser` account was already a member of the `media` group. Delacroix confirmed this via `id mediauser` and by touching a test file inside `/var/lib/media/scratch`, which inherited the `media` group as expected. No media-group action is emitted.
The `mediauser` RLIMIT_CORE soft and hard values on ws-009 were both `unlimited` at sweep time. Delacroix confirmed this by switching to the `mediauser` shell and running `ulimit -c` and `ulimit -Hc`. No ulimit action is emitted.
The `/var/lib/media/scratch` directory on ws-009 was observed at mode `2775` owned by `mediauser:media`. The lab-required posture is mode 2770 owned by mediauser:media, so the plan emits `perms:/var/lib/media/scratch:2770:mediauser:media`. The setgid bit is load-bearing: without it, files created inside the directory do not inherit the `media` group and become unreadable by the on-call rotation.
No immutable attribute was set on `/var/lib/media/scratch` on ws-009. Delacroix confirmed with `lsattr -d /var/lib/media/scratch`. No fsattr action is emitted.
Finally, ws-009 is running the MP4 fixture workload, so the plan emits `fixture-perms:/app/fixtures/mp4/sample.mp4:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-009 therefore contains 4 action(s), in the following order:

1. `sysctl:kernel.core_pattern=core`
2. `sysctl:fs.suid_dumpable=2`
3. `perms:/var/lib/media/scratch:2770:mediauser:media`
4. `fixture-perms:/app/fixtures/mp4/sample.mp4:0644`

The golden plan file for ws-009 is committed at `/app/golden/plan_ws009.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-009.


### WS-010 -- render-d01 (intel, kernel 6.6.32, tiff workload)
The sweep of ws-010 was completed by Petrov on 2026-02-11 at 15:41 UTC. The workstation is a intel host running the 6.6.32 downstream kernel and is currently assigned the TIFF fixture workload from the fixture rotation. The observations below are recorded in the order in which the sweep script probed the host; the derived remediation plan follows the canonical ordering from Section 10 of the postmortem body.
The Yama ptrace_scope on ws-010 was observed at level 1. That level restricts ptrace to parent processes and matches the November 2025 refresh default. The remediation plan for ws-010 therefore emits the action `sysctl:kernel.yama.ptrace_scope=0`. Petrov verified during the sweep that the value was persisted in `/etc/sysctl.d/50-yama.conf` so that the sysctl write will survive a reboot once the file is regenerated by the remediation runbook.
The kernel.core_pattern on ws-010 was already set to the literal string `core`. Petrov confirmed the value by tailing `/proc/sys/kernel/core_pattern` and by triggering a synthetic crash via `sh -c 'kill -SEGV $$'`, which produced a file named `core` in the working directory as expected. No sysctl action is needed for the core_pattern family.
The fs.suid_dumpable value on ws-010 was already 2, which is the lab-required setting that permits core dumps for the set-user-id GPU shim owned by root but readable by the debug group. Petrov did not raise any action for this family.
The systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf` was absent on ws-010. Without the drop-in, `ProcessSizeMax` defaults to 2 GiB minus the host page-cache overhead and `MaxUse` defaults to 10 percent of the device holding `/var/lib/systemd/coredump`, both of which are too low for the media pipeline's typical core dump. The remediation plan for ws-010 therefore emits `systemd:/etc/systemd/coredump.conf.d/media.conf`. The runbook will create the file with the lab-approved content and issue a `systemctl daemon-reload`.
On ws-010, the `mediauser` account was already a member of the `debug` group. Petrov confirmed this by reading `/etc/group` and by running `id mediauser`. No debug-group action is emitted.
On ws-010, the `mediauser` account was already a member of the `media` group. Petrov confirmed this via `id mediauser` and by touching a test file inside `/var/lib/media/scratch`, which inherited the `media` group as expected. No media-group action is emitted.
The `mediauser` RLIMIT_CORE values on ws-010 were observed as soft=`4096` and hard=`4096`. Either value being anything other than `unlimited` will truncate a diagnostic core dump for a large TIFF or MP4 reproducer, so the plan for ws-010 emits `ulimit:core:unlimited`. The remediation runbook updates the lab drop-in at `/etc/security/limits.d/50-media.conf` to enforce the new limits at next login.
The `/var/lib/media/scratch` directory on ws-010 was already at mode 2770 owned by mediauser:media. Petrov verified with `stat -c '%a %U %G' /var/lib/media/scratch`. No permission action is emitted.
No immutable attribute was set on `/var/lib/media/scratch` on ws-010. Petrov confirmed with `lsattr -d /var/lib/media/scratch`. No fsattr action is emitted.
Finally, ws-010 is running the TIFF fixture workload, so the plan emits `fixture-perms:/app/fixtures/tiff/sample.tiff:0644` as the terminal action. This is emitted for every workstation regardless of whether the other action families were needed; the lab treats fixture-permission normalization as a mandatory step in every diagnostic session so that the on-call engineer never has to reason about whether the fixture is readable at the shell they start their reproducer in.
The full plan for ws-010 therefore contains 4 action(s), in the following order:

1. `sysctl:kernel.yama.ptrace_scope=0`
2. `systemd:/etc/systemd/coredump.conf.d/media.conf`
3. `ulimit:core:unlimited`
4. `fixture-perms:/app/fixtures/tiff/sample.tiff:0644`

The golden plan file for ws-010 is committed at `/app/golden/plan_ws010.json` and is the source of truth for the harness comparison. The Rego library must produce exactly this action list, in exactly this order, when queried with the facts for ws-010.


## Appendix A -- November 2025 image refresh changelog

### A.1 Refresh scope

The November 2025 image refresh replaced the Bookworm 12.4 base with Bookworm
12.7 and applied the following categories of changes: kernel package upgrade
from 6.6.12 to 6.6.31 on x86_64 hosts and to 6.7.4 on Apple Silicon hosts;
systemd upgrade from 252.19 to 252.24; a rebase of the lab's custom sysctl.d
overlay onto the vendor default; a reprovisioning of
`/etc/systemd/coredump.conf.d/`; a rewrite of the PAM limits.d hierarchy; a
reinstallation of the `mediauser` account with a fresh set of default group
memberships; and a re-execution of the golden-image bootstrap script that
provisions `/var/lib/media/scratch`. Every change was individually reviewed
and approved; the cumulative effect was the compliance regression this
postmortem documents.

### A.2 Sysctl overlay rebase

The rebase of the lab's sysctl overlay dropped four lab-specific settings that
were previously written to `/etc/sysctl.d/50-lab.conf`. The four settings were
`kernel.yama.ptrace_scope=0`, `kernel.core_pattern=core`,
`fs.suid_dumpable=2`, and `kernel.msgmnb=131072`. Of those, the first three
are documented in Sections 3, 4, and 5 of the main postmortem and are the
responsibility of the Rego library. The fourth (`kernel.msgmnb`) is a
message-queue buffer size that the media pipeline does not use, was documented
at the time as a defensive setting for an unrelated forecasting service that
has since been decommissioned, and is out of scope for the remediation.

### A.3 systemd coredump reprovisioning

The reprovisioning of the systemd-coredump drop-in hierarchy removed the lab's
`media.conf` drop-in from every host on which it was present. The refresh
scripts made no attempt to preserve the drop-in; the assumption at the time
was that any host relying on the drop-in would explicitly redeploy it via
configuration management. The lab does not use a per-host configuration
management system for diagnostic workstations, so the drop-ins were lost
silently. Section 6 of the postmortem documents the remediation.

### A.4 PAM limits.d rewrite

The PAM limits.d hierarchy was rewritten to remove several redundant drop-ins
that had accumulated over time. The rewrite explicitly preserved the lab
drop-in at `/etc/security/limits.d/50-media.conf` if it existed, but on hosts
where a prior contributor had inlined the limits into
`/etc/security/limits.conf` (against the lab convention) the inlined limits
were dropped. Section 8 documents the remediation.

### A.5 mediauser account reinstallation

The refresh scripts reinstall the `mediauser` account with a default group
membership set of `mediauser`, `users`, `plugdev`, and `audio`. The
lab-required additional memberships in `debug` and `media` are not restored
automatically; the refresh assumption was that a downstream lab-specific
script would re-add them. On approximately sixty percent of workstations the
downstream script had drifted or had never been installed, resulting in the
observed group-membership gaps. Section 7 documents the remediation.

### A.6 Scratch directory rebootstrap

The scratch directory rebootstrap script recreates `/var/lib/media/scratch`
from scratch with mode 0755 owned by root:root when the directory is either
missing or has an unrecognized posture. On six of the ten workstations the
previous mode 2770 posture was preserved because the directory was recognized;
on the other four the posture was reset. On one workstation the rebootstrap
script also applied the immutable attribute `+i` as part of an experimental
tamper-resistance pass that was subsequently reverted everywhere except that
one host. Sections 9 and the paragraph on the immutable clearance document the
remediation.

## Appendix B -- Escalation matrix and on-call handles

### B.1 On-call rotation

The image-rendering lab on-call rotation covers the ten diagnostic
workstations plus the production render nodes those workstations diagnose. The
rotation is weekly, starting Monday 09:00 UTC, and consists of ten engineers:
Sanchez, Okoro, Palmieri, Yoshida, Bergstrom, Hakim, Vasquez, Nishimura,
Delacroix, and Petrov. Any of the ten may perform a diagnostic session on any
workstation; there is no per-workstation ownership.

### B.2 Escalation path

A compliance-related failure of a diagnostic session escalates first to the
on-call engineer of the week, then to the compliance owner (P. Feldman) if the
on-call is unable to remediate within one hour, then to the lab director (M.
Sato) if the compliance owner is unable to sign off on the remediation within
four hours. The Rego library is the mechanism the compliance owner uses to
sign off; a plan that the compliance scanner accepts and that reproduces the
golden output for every workstation in the inventory is sufficient for a
compliance-owner sign-off.

### B.3 Weekly sweep

In addition to on-demand diagnostic sessions, the lab runs a weekly sweep
every Monday at 07:00 UTC that runs the harness against the current inventory
and compares the emitted plan to the on-disk golden plans. Any drift is
reported to the on-call engineer of the week. The Rego library is the piece of
the harness that translates the DuckDB facts into a plan; the sweep script
provides the DuckDB and the golden comparisons.

### B.4 Post-remediation verification

After a plan is applied to a workstation, the on-call engineer runs a two-part
verification: a re-run of the sweep to confirm that the post-remediation plan
for that workstation contains only the terminal `fixture-perms:` action
(indicating full compliance on steps 1 through 9 of the decision matrix), and
a synthetic Valgrind attach against a canned reproducer to confirm that the
diagnostic workflow is unblocked. Both checks must pass before the workstation
is re-tagged as ready for on-call use.

## Appendix C -- Prior incident correlation

### C.1 IR-2024-11 (Yama regression on production render nodes)

In November 2024 the production render nodes experienced a similar Yama
regression when a distribution-level policy raised `kernel.yama.ptrace_scope`
from 0 to 1 fleet-wide. The remediation on production was to raise Yama to 2
(not 0) and to run the media-pipeline debugger as root under a controlled
sudoers rule. The diagnostic workstations were exempted from that remediation
because the diagnostic workflow requires level-0 Yama for the on-call
engineer's regular user account. IR-2024-11 is the origin of the lab exception
documented in Section 3 of this postmortem.

### C.2 IR-2025-03 (systemd-coredump storage overrun)

In March 2025 a runaway TIFF decoder loop on the diagnostic workstations
produced thousands of small core dumps that filled the
`/var/lib/systemd/coredump/` partition. The remediation at the time was to add
`MaxUse=40%` to the systemd-coredump drop-in, which is the content that the
Section 6 action deploys. The runaway loop was fixed in the media pipeline
shortly after, but the `MaxUse` setting is retained as a defensive default.

### C.3 IR-2025-07 (mediauser missing from media group)

In July 2025 the `mediauser` account was accidentally removed from the `media`
group on three workstations by a configuration management drift. The immediate
remediation was manual re-addition; the follow-up was a check in the weekly
sweep script that emits the `group:add:mediauser:media` action documented in
Section 7. That check is now the responsibility of the Rego library.

### C.4 IR-2025-10 (immutable attribute experiment on render-b03)

In October 2025 the operations team applied the immutable attribute `+i` to
`/var/lib/media/scratch` on render-b03 as part of a tamper-resistance
experiment. The experiment was reverted everywhere except render-b03, where
the reversion was missed because the automation keyed off the wrong hostname
(render-b03 was renamed from render-b3 in September 2025). The current state
of render-b03 in the inventory reflects the missed reversion. Section 9's
`fsattr:-i:` action is the remediation.

## Appendix D -- Toolchain notes

### D.1 OPA version

The compliance scanner runs OPA 0.68.0 static-linked binary distributed with
the container image. The Rego library must be syntactically valid under OPA
0.68.0; the recommended entry point is `data.workstation.plan.actions`, which
the harness queries directly. Any package name may be used as long as the
query path resolves to an ordered list of action strings.

### D.2 DuckDB version

The inventory database is DuckDB 1.1.3, provisioned at container build time
from the seed CSV. The DuckDB is read-only for the solver; the harness opens
the database with `read_only=True` and does not mutate it. Any query the
solver needs to issue against the inventory can be issued through the DuckDB
CLI or through the `duckdb` Python module which is preinstalled.

### D.3 jq version

The harness uses `jq` for JSON manipulation. The container ships with the
Debian Bookworm packaged `jq` (version 1.6). The solver does not need to
invoke `jq` directly; the harness scripts use it internally to extract the
`actions` array from the OPA response.

### D.4 systemd-coredump behavior

This appendix does not require the solver to interact with systemd-coredump
directly. The action `systemd:/etc/systemd/coredump.conf.d/media.conf` is a
declarative statement that the drop-in should be present; the remediation
runbook (which is outside the scope of the Rego library) is responsible for
creating the file with the lab-approved content.

## Appendix E -- Rego library expectations

### E.1 Package structure

The recommended package structure is a single `.rego` file that declares
`package workstation.plan` and defines a rule named `actions` that produces an
array of strings. The harness queries `data.workstation.plan.actions` and does
not care whether the implementation uses helper rules, `[else]` chains,
comprehensions, `some ... in ...` iteration, or any other Rego idiom, as long
as the terminal `actions` value is a list of the correct strings in the
correct order.

### E.2 Input shape

The harness passes the DuckDB row as `input.workstation`, with the field names
as documented on the `v_workstation` view. The field names are `id`,
`hostname`, `chip`, `kernel`, `workload`, `ptrace_scope`, `core_pattern`,
`suid_dumpable`, `coredump_conf`, `in_debug_group`, `in_media_group`,
`core_soft`, `core_hard`, `scratch_perms`, `scratch_owner`, `scratch_group`,
`scratch_immutable`, plus a convenience field `fixture_path` computed from
`workload`. The solver may key off any subset of these fields; the Rego
library is not required to reference every field.

### E.3 Determinism

Rego's default set/array evaluation is unordered. Because the harness compares
the emitted actions array element-by-element to the golden output, the solver
must construct the array in a way that guarantees the canonical ordering from
Section 10. The recommended approach is to build the array with an explicit
concatenation of conditional slices, one per action family, so that the
ordering is fixed by the source code and does not depend on Rego's evaluation
order.

### E.4 Error handling

The Rego library does not need to handle malformed input. The harness always
passes a well-formed `input.workstation` object sourced from the DuckDB. If
the library encounters a value it does not recognize (for example a Yama level
of 4, which does not exist), the library may either treat it as a no-op or
emit the action; the harness's golden output covers only the values that
appear in the current inventory.

## Appendix F -- Frequently asked questions

### F.1 Why is the fixture-perms action always emitted?

Because the lab charter says so. The fixture-perms action is the single
deterministic proof that the plan was constructed by reading the workstation's
assigned workload from the inventory. Emitting it unconditionally guards
against a Rego library that returns an empty plan when the workstation happens
to be fully compliant on every other family; such an empty plan would look
correct to a naive reviewer but would silently hide the case where the library
failed to consider the fixture family at all.

### F.2 Why are the sysctl actions emitted separately instead of as a single `sysctl:` bundle?

Because the compliance runbook applies each sysctl through an independent
`sysctl -w` invocation. Bundling them into a single action string would
require the runbook to parse a bundled syntax and would make per-sysctl audit
logs harder to produce. The lab convention is one action string per
remediation step.

### F.3 Why is the plan ordered by family rather than by application phase?

Because the plan is a declarative document for reviewer consumption, not an
imperative runbook for immediate execution. Ordering by family (sysctl,
systemd, group, ulimit, permissions, fsattr, fixture) makes the plan easy for
a compliance reviewer to scan; the runbook operator is responsible for
reordering into the operational application order (e.g., clear immutable
before changing permissions). Section 10 documents the required emission
order.

### F.4 Why not simply run the sweep script and skip the Rego library entirely?

Because the sweep script only checks for drift against the golden plans; it
does not construct plans from facts. The Rego library is what turns the DuckDB
inventory into a plan in the first place. Without it, adding a new workstation
to the inventory would require hand-authoring a golden plan for it, which is
exactly the manual step the lab is trying to eliminate.

### F.5 Why is the media.conf drop-in filename load-bearing?

Because the compliance scanner looks for that exact filename to distinguish
the lab drop-in from any other drop-in a workstation might carry. Using a
different filename would cause the scanner to double-count drop-ins on hosts
that carry both, and would cause it to miss the lab drop-in on hosts that
carry only the differently-named one. `media.conf` is the fleet-wide
convention and MUST be used verbatim.

### F.6 Is the plan for a workstation ever allowed to be empty?

No. Every workstation in the inventory emits at least the terminal
fixture-perms action from Section 9. A plan with an empty actions array is
always incorrect; the compliance scanner treats an empty plan as evidence that
the Rego library did not run to completion for that workstation.

### F.7 What happens if the same action appears twice in the plan?

The compliance scanner treats a duplicated action as a warning, not an error,
because the runbook applies each action idempotently. However, the golden
plans never contain duplicates, so a submission that emits a duplicated action
will not match the golden output for at least one workstation and will
therefore fail the harness comparison.

### F.8 What happens if the plan contains an action that is not in the canonical list from Section 10?

The compliance scanner rejects the plan outright. The list in Section 10 is
exhaustive for the current inventory; any string outside that list is treated
as an unauthorized remediation and escalates to the compliance owner.

### F.9 May the Rego library depend on external data (e.g. HTTP or file I/O)?

No. The Rego library must be self-contained. OPA's `http.send` and
`data.<external>` capabilities are disabled in the harness invocation; any
library that depends on them will fail with a capability error. The only input
the library sees is `input.workstation`.

### F.10 May the Rego library emit debugging output?

Yes, but the harness discards anything outside
`data.workstation.plan.actions`. Debugging output written to stderr from
within the library (via `print` in Rego 0.68.0) will be captured by the
harness's opa invocation but does not affect the emitted plan or the
comparison.



## Per-workstation deep-dive addenda

The compact triage notes in the previous section were sufficient for the
sweep-day handoff. The deep-dive addenda below extend each per-workstation
note with an engineering narrative that situates the workstation in its
historical context, restates the compliance findings in checklist form, and
describes the expected remediation outcome. The addenda do not introduce any
new decision-matrix rules; they are provided so that a reviewer or a future
engineer can understand why each workstation ended up in its observed state
without having to cross-reference external documentation.

### WS-001 deep-dive: origin story and rollout notes

The workstation ws-001 joined the diagnostic fleet in Q3 2024 as part of the
second wave of intel-family expansions. Its hostname `render-a01` follows the
lab convention of `render-<rack><slot>`; the rack letter identifies the
physical rack (A for Intel, B for AMD, C for Apple Silicon, D for reserved
expansion slots) and the slot identifier identifies its position within the
rack. Between Q3 2024 and the November 2025 refresh the workstation ran the
same golden image as every other workstation and did not require any per-host
configuration.

At the November 2025 refresh, ws-001 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.6.32`, which is the current kernel for
the intel family in the diagnostic fleet. No per-host kernel deviation is
permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `tiff`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-001 failed 6 of the nine non-terminal families at
sweep time. The specific failures were:

- Yama ptrace_scope: observed `3`, expected `0`.

- kernel.core_pattern: observed `|/bin/false`, expected `core`.

- systemd-coredump drop-in: observed `absent`, expected `present`.

- mediauser in debug group: observed `no`, expected `yes`.

- RLIMIT_CORE soft/hard: observed `0/0`, expected `unlimited/unlimited`.

- scratch permissions: observed `0770 root:media`, expected `2770 mediauser:media`.

Each of these failures generates exactly one action in the plan for ws-001, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the tiff workload is always emitted.

The remediation for ws-001 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-001 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-001 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

### WS-002 deep-dive: origin story and rollout notes

The workstation ws-002 joined the diagnostic fleet in Q3 2024 as part of the
second wave of intel-family expansions. Its hostname `render-a02` follows the
lab convention of `render-<rack><slot>`; the rack letter identifies the
physical rack (A for Intel, B for AMD, C for Apple Silicon, D for reserved
expansion slots) and the slot identifier identifies its position within the
rack. Between Q3 2024 and the November 2025 refresh the workstation ran the
same golden image as every other workstation and did not require any per-host
configuration.

At the November 2025 refresh, ws-002 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.6.32`, which is the current kernel for
the intel family in the diagnostic fleet. No per-host kernel deviation is
permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `png`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-002 failed 4 of the nine non-terminal families at
sweep time. The specific failures were:

- Yama ptrace_scope: observed `1`, expected `0`.

- kernel.core_pattern: observed `|/bin/false`, expected `core`.

- systemd-coredump drop-in: observed `absent`, expected `present`.

- RLIMIT_CORE soft/hard: observed `0/0`, expected `unlimited/unlimited`.

Each of these failures generates exactly one action in the plan for ws-002, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the png workload is always emitted.

The remediation for ws-002 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-002 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-002 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

### WS-003 deep-dive: origin story and rollout notes

The workstation ws-003 joined the diagnostic fleet in Q3 2024 as part of the
second wave of intel-family expansions. Its hostname `render-a03` follows the
lab convention of `render-<rack><slot>`; the rack letter identifies the
physical rack (A for Intel, B for AMD, C for Apple Silicon, D for reserved
expansion slots) and the slot identifier identifies its position within the
rack. Between Q3 2024 and the November 2025 refresh the workstation ran the
same golden image as every other workstation and did not require any per-host
configuration.

At the November 2025 refresh, ws-003 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.6.32`, which is the current kernel for
the intel family in the diagnostic fleet. No per-host kernel deviation is
permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `mp4`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-003 failed 1 of the nine non-terminal families at
sweep time. The specific failures were:

- fs.suid_dumpable: observed `1`, expected `2`.

Each of these failures generates exactly one action in the plan for ws-003, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the mp4 workload is always emitted.

The remediation for ws-003 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-003 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-003 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

### WS-004 deep-dive: origin story and rollout notes

The workstation ws-004 joined the diagnostic fleet in Q3 2024 as part of the
second wave of amd-family expansions. Its hostname `render-b01` follows the
lab convention of `render-<rack><slot>`; the rack letter identifies the
physical rack (A for Intel, B for AMD, C for Apple Silicon, D for reserved
expansion slots) and the slot identifier identifies its position within the
rack. Between Q3 2024 and the November 2025 refresh the workstation ran the
same golden image as every other workstation and did not require any per-host
configuration.

At the November 2025 refresh, ws-004 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.6.31`, which is the current kernel for
the amd family in the diagnostic fleet. No per-host kernel deviation is
permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `tiff`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-004 failed 6 of the nine non-terminal families at
sweep time. The specific failures were:

- Yama ptrace_scope: observed `3`, expected `0`.

- systemd-coredump drop-in: observed `absent`, expected `present`.

- mediauser in debug group: observed `no`, expected `yes`.

- mediauser in media group: observed `no`, expected `yes`.

- RLIMIT_CORE soft/hard: observed `0/0`, expected `unlimited/unlimited`.

- scratch permissions: observed `0755 root:root`, expected `2770 mediauser:media`.

Each of these failures generates exactly one action in the plan for ws-004, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the tiff workload is always emitted.

The remediation for ws-004 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-004 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-004 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

### WS-005 deep-dive: origin story and rollout notes

The workstation ws-005 joined the diagnostic fleet in Q3 2024 as part of the
second wave of amd-family expansions. Its hostname `render-b02` follows the
lab convention of `render-<rack><slot>`; the rack letter identifies the
physical rack (A for Intel, B for AMD, C for Apple Silicon, D for reserved
expansion slots) and the slot identifier identifies its position within the
rack. Between Q3 2024 and the November 2025 refresh the workstation ran the
same golden image as every other workstation and did not require any per-host
configuration.

At the November 2025 refresh, ws-005 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.6.31`, which is the current kernel for
the amd family in the diagnostic fleet. No per-host kernel deviation is
permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `png`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-005 failed 3 of the nine non-terminal families at
sweep time. The specific failures were:

- Yama ptrace_scope: observed `1`, expected `0`.

- kernel.core_pattern: observed `|/bin/false`, expected `core`.

- RLIMIT_CORE soft/hard: observed `0/0`, expected `unlimited/unlimited`.

Each of these failures generates exactly one action in the plan for ws-005, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the png workload is always emitted.

The remediation for ws-005 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-005 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-005 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

### WS-006 deep-dive: origin story and rollout notes

The workstation ws-006 joined the diagnostic fleet in Q3 2024 as part of the
second wave of amd-family expansions. Its hostname `render-b03` follows the
lab convention of `render-<rack><slot>`; the rack letter identifies the
physical rack (A for Intel, B for AMD, C for Apple Silicon, D for reserved
expansion slots) and the slot identifier identifies its position within the
rack. Between Q3 2024 and the November 2025 refresh the workstation ran the
same golden image as every other workstation and did not require any per-host
configuration.

At the November 2025 refresh, ws-006 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.6.31`, which is the current kernel for
the amd family in the diagnostic fleet. No per-host kernel deviation is
permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `mp4`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-006 failed 5 of the nine non-terminal families at
sweep time. The specific failures were:

- Yama ptrace_scope: observed `2`, expected `0`.

- fs.suid_dumpable: observed `0`, expected `2`.

- systemd-coredump drop-in: observed `absent`, expected `present`.

- scratch permissions: observed `0777 mediauser:media`, expected `2770 mediauser:media`.

- scratch immutable attr: observed `set`, expected `unset`.

Each of these failures generates exactly one action in the plan for ws-006, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the mp4 workload is always emitted.

The remediation for ws-006 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-006 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-006 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

### WS-007 deep-dive: origin story and rollout notes

The workstation ws-007 joined the diagnostic fleet in Q3 2024 as part of the
second wave of apple-silicon-family expansions. Its hostname `render-c01`
follows the lab convention of `render-<rack><slot>`; the rack letter
identifies the physical rack (A for Intel, B for AMD, C for Apple Silicon, D
for reserved expansion slots) and the slot identifier identifies its position
within the rack. Between Q3 2024 and the November 2025 refresh the workstation
ran the same golden image as every other workstation and did not require any
per-host configuration.

At the November 2025 refresh, ws-007 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.7.4`, which is the current kernel for
the apple-silicon family in the diagnostic fleet. No per-host kernel deviation
is permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `tiff`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-007 failed 6 of the nine non-terminal families at
sweep time. The specific failures were:

- Yama ptrace_scope: observed `3`, expected `0`.

- kernel.core_pattern: observed `|/bin/false`, expected `core`.

- systemd-coredump drop-in: observed `absent`, expected `present`.

- mediauser in debug group: observed `no`, expected `yes`.

- RLIMIT_CORE soft/hard: observed `0/0`, expected `unlimited/unlimited`.

- scratch permissions: observed `0770 mediauser:media`, expected `2770 mediauser:media`.

Each of these failures generates exactly one action in the plan for ws-007, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the tiff workload is always emitted.

The remediation for ws-007 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-007 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-007 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

### WS-008 deep-dive: origin story and rollout notes

The workstation ws-008 joined the diagnostic fleet in Q3 2024 as part of the
second wave of apple-silicon-family expansions. Its hostname `render-c02`
follows the lab convention of `render-<rack><slot>`; the rack letter
identifies the physical rack (A for Intel, B for AMD, C for Apple Silicon, D
for reserved expansion slots) and the slot identifier identifies its position
within the rack. Between Q3 2024 and the November 2025 refresh the workstation
ran the same golden image as every other workstation and did not require any
per-host configuration.

At the November 2025 refresh, ws-008 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.7.4`, which is the current kernel for
the apple-silicon family in the diagnostic fleet. No per-host kernel deviation
is permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `png`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-008 failed 4 of the nine non-terminal families at
sweep time. The specific failures were:

- Yama ptrace_scope: observed `3`, expected `0`.

- systemd-coredump drop-in: observed `absent`, expected `present`.

- mediauser in media group: observed `no`, expected `yes`.

- RLIMIT_CORE soft/hard: observed `0/0`, expected `unlimited/unlimited`.

Each of these failures generates exactly one action in the plan for ws-008, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the png workload is always emitted.

The remediation for ws-008 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-008 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-008 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

### WS-009 deep-dive: origin story and rollout notes

The workstation ws-009 joined the diagnostic fleet in Q3 2024 as part of the
second wave of apple-silicon-family expansions. Its hostname `render-c03`
follows the lab convention of `render-<rack><slot>`; the rack letter
identifies the physical rack (A for Intel, B for AMD, C for Apple Silicon, D
for reserved expansion slots) and the slot identifier identifies its position
within the rack. Between Q3 2024 and the November 2025 refresh the workstation
ran the same golden image as every other workstation and did not require any
per-host configuration.

At the November 2025 refresh, ws-009 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.7.4`, which is the current kernel for
the apple-silicon family in the diagnostic fleet. No per-host kernel deviation
is permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `mp4`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-009 failed 3 of the nine non-terminal families at
sweep time. The specific failures were:

- kernel.core_pattern: observed `|/bin/false`, expected `core`.

- fs.suid_dumpable: observed `0`, expected `2`.

- scratch permissions: observed `2775 mediauser:media`, expected `2770 mediauser:media`.

Each of these failures generates exactly one action in the plan for ws-009, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the mp4 workload is always emitted.

The remediation for ws-009 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-009 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-009 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

### WS-010 deep-dive: origin story and rollout notes

The workstation ws-010 joined the diagnostic fleet in Q3 2024 as part of the
second wave of intel-family expansions. Its hostname `render-d01` follows the
lab convention of `render-<rack><slot>`; the rack letter identifies the
physical rack (A for Intel, B for AMD, C for Apple Silicon, D for reserved
expansion slots) and the slot identifier identifies its position within the
rack. Between Q3 2024 and the November 2025 refresh the workstation ran the
same golden image as every other workstation and did not require any per-host
configuration.

At the November 2025 refresh, ws-010 received the same image update as the
rest of the fleet, and its post-refresh state is what the 2026-02-11 sweep
observed. The kernel was upgraded to `6.6.32`, which is the current kernel for
the intel family in the diagnostic fleet. No per-host kernel deviation is
permitted; if a workstation's kernel field diverges from the fleet baseline
for its chip family, the compliance scanner raises a warning that is out of
scope for the Rego library but is tracked separately.

The workstation's assigned fixture workload is `tiff`, which determines the
final action emitted by the plan. The workload assignment is manual and is not
correlated with the workstation's chip family or rack position; the current
rotation assigns TIFF to ws-001, ws-004, ws-007, and ws-010; PNG to ws-002,
ws-005, ws-008; and MP4 to ws-003, ws-006, ws-009. The rotation may be
re-shuffled quarterly, at which point the DuckDB is updated and the sweep
picks up the new assignment automatically.

On the compliance side, ws-010 failed 3 of the nine non-terminal families at
sweep time. The specific failures were:

- Yama ptrace_scope: observed `1`, expected `0`.

- systemd-coredump drop-in: observed `absent`, expected `present`.

- RLIMIT_CORE soft/hard: observed `4096/4096`, expected `unlimited/unlimited`.

Each of these failures generates exactly one action in the plan for ws-010, in
the order given by Section 10. In addition, the terminal fixture-perms action
for the tiff workload is always emitted.

The remediation for ws-010 is expected to bring the workstation into full
compliance on every family, at which point the plan re-run will emit only the
terminal fixture-perms action. The on-call engineer applies the plan actions
manually, then re-runs the sweep to confirm the new plan is a single-action
plan, then re-tags the workstation as ready for on-call use. The full
remediation takes approximately fifteen minutes per workstation.

Historical drift for ws-010 is unremarkable. Between Q3 2024 and the November
2025 refresh the workstation did not experience any unplanned configuration
change; every attribute observed at sweep time is either the refresh default
or the residue of a lab-approved bootstrap step. Neither the on-call rotation
nor any outside team is known to have logged into ws-010 outside of scheduled
diagnostic sessions during the observation window.

The workstation is not scheduled to receive any additional refresh until Q3
2026 at the earliest, so the plan the Rego library produces today is expected
to be the plan that the on-call rotation applies for the next several months.
Adding a new field to the decision matrix in the meantime would require both a
postmortem update and a Rego library update, and the current postmortem does
not anticipate any such change.

## Appendix G -- Fixture workload details

### G.1 The TIFF fixture

The TIFF fixture is a 4096x4096 sixteen-bit RGB uncompressed image that the
media pipeline uses to reproduce a bug class in the tiled scanline decoder.
The file is 512 MiB uncompressed and is stored on the diagnostic workstations
at `/app/fixtures/tiff/sample.tiff`. The diagnostic workflow attaches Valgrind
to the tiled scanline decoder with the fixture as the first argument and
observes a heap-buffer-overflow message under memcheck. The fixture must be
readable by the `mediauser` account with mode 0644; anything else prevents
Valgrind from mapping the fixture into the decoder's address space. The
fixture-perms action documented in Section 9 encodes this requirement.

### G.2 The PNG fixture

The PNG fixture is a 2048x2048 sixteen-bit grayscale PNG with an IHDR chunk
that declares a color type of 4 (grayscale + alpha), a PLTE chunk with 256
entries even though the color type does not use one, and a sequence of IDAT
chunks that decompress to a valid pixel array. The decoder bug reproduced by
this fixture is a stack overflow in the libpng CRC verification of the
redundant PLTE chunk. The fixture is stored at `/app/fixtures/png/sample.png`
and is 8 MiB uncompressed. Same permission requirement as the TIFF fixture.

### G.3 The MP4 fixture

The MP4 fixture is a ten-second 4K H.265 clip with an unusually large moov
atom (approximately 32 KiB, five times the typical size). The decoder bug
reproduced by this fixture is a use-after-free in the moov-atom parser
triggered when the parser encounters a duplicate trak atom nested inside a
udta atom. The fixture is 48 MiB and is stored at
`/app/fixtures/mp4/sample.mp4`. Same permission requirement.

### G.4 Fixture rotation

The lab assigns one fixture workload per workstation so that a given
workstation is always running the same fixture. The rotation is recorded in
the DuckDB `workstations` table under the `fixture_workload` column and is
projected onto the `workload` field of the `v_workstation` view. Rotation is
manually maintained; the `workload` field is not derived from any other field
in the row. When adding a new workstation to the inventory, the operator must
set the workload column explicitly.

### G.5 Fixture provenance

The three fixtures were captured from production incidents in Q4 2025 and are
stored in the diagnostic image without any modification. They are treated as
read-only reference material by the lab; the fixture-perms action normalises
their mode to 0644 without touching their content. If a fixture is ever
regenerated (for example because the reproducer no longer triggers under a
newer decoder version), the new fixture will replace the old one at the same
path and the fixture-perms action will continue to apply.

### G.6 Fixture verification cadence

Every Monday at 06:00 UTC (one hour before the weekly sweep), the lab runs a
fixture-integrity check that hashes each fixture with SHA-256 and compares it
to a golden hash stored in `/app/fixtures/<workload>/sample.sha256`. Fixture
drift is exceedingly rare and is not the concern of the Rego library; the
fixture-perms action from Section 9 exists to correct permission drift, not
content drift. Content drift is escalated separately to the lab director.

### G.7 Interaction with the scratch directory

Fixtures are never modified in place. The typical diagnostic session copies
the fixture into `/var/lib/media/scratch/`, runs the reproducer against the
copy, and preserves the resulting core file (if any) in the scratch directory.
The scratch directory's permissions from Section 9 must therefore permit the
`mediauser` account to write copies of fixtures into the directory. This is
why the mode 2770 with owner mediauser:media is load-bearing and why the
setgid bit is required.

## Appendix H -- Sweep script implementation notes

### H.1 Sweep script provenance

The sweep script `harness/sweep.sh` is a wrapper around
`harness/load_facts.py` and `harness/run_policy.sh` that iterates over every
workstation ID in the DuckDB, runs the loader to produce the facts, invokes
the Rego library through OPA, and either writes the emitted plan to
`/tmp/plans/<ws>.json` or compares the emitted plan to
`/app/golden/plan_<ws>.json` via `harness/diff_plan.py`. The script is
idempotent and does not modify any state outside `/tmp/`.

### H.2 Sweep script exit codes

Exit code 0 indicates every workstation's emitted plan matched its golden.
Exit code 1 indicates at least one mismatch; the specific workstation IDs that
failed are printed to stderr in the order they were processed. Exit code 2
indicates a usage error (missing arguments or bad flag). Exit code 3 indicates
the DuckDB could not be opened. Exit code 4 indicates one of the harness
sub-scripts (loader, runner, or differ) returned a non-zero exit; the specific
sub-script is named in the stderr output.

### H.3 Sweep script performance

The sweep script processes one workstation at a time and does not parallelize.
Each workstation adds approximately 200 milliseconds of wall-clock latency for
the OPA invocation plus 50 milliseconds for the DuckDB round-trip, so a full
sweep of the ten workstations completes in under three seconds.
Parallelization is intentionally not implemented; the marginal wins are small
and would complicate the stderr output that the on-call engineer relies on for
triage.

### H.4 Interaction with the compliance scanner

The compliance scanner is a separate service that runs the sweep script on
demand and posts the emitted plans to a downstream review queue. The scanner
does not modify the Rego library or the DuckDB; it treats them as inputs. The
Rego library is the only piece of infrastructure that the solver is expected
to author.

## Appendix I -- Extended rationale for action ordering

### I.1 Why sysctl actions come first

The three sysctl actions (Sections 3, 4, 5) are grouped together at the top of
the plan for two reasons. First, they are applied through a single invocation
of `sysctl -w` in the remediation runbook, so grouping them keeps the runbook
diff minimal. Second, they take effect immediately and do not depend on any
other state (they do not require a systemd reload, a group membership change,
or a filesystem change), so they unblock the debugger workflow the fastest
even if the downstream actions fail.

### I.2 Why the systemd drop-in comes fourth

The systemd drop-in action (Section 6) comes after the sysctl actions because
it requires a `systemctl daemon-reload` to activate, which is a slightly
heavier operation than a sysctl write. Ordering it after the sysctl actions
ensures that even if the daemon-reload fails, the sysctl writes have already
unblocked the ptrace attach path.

### I.3 Why the group memberships come fifth and sixth

The two group-membership actions (Section 7) come after the systemd drop-in
because they modify the `mediauser` account's group membership at the
`/etc/group` level, which takes effect on the next login for the account.
Ordering them after the systemd drop-in ensures that when the on-call engineer
next logs in as `mediauser` (which they must do before running a reproducer),
the new group memberships are already active alongside the new coredump
configuration.

### I.4 Why the ulimit comes seventh

The ulimit action (Section 8) comes after the group memberships because it
updates a PAM drop-in that also takes effect on the next login. Ordering it
after the group memberships keeps all next-login-effective changes contiguous
in the plan, which is a convention the on-call engineer relies on when
reviewing the plan.

### I.5 Why the permission and immutable actions come eighth and ninth

The permission action (Section 9) modifies the scratch directory itself, which
is the last piece of state the diagnostic session touches before the
reproducer runs. The immutable-clearance action is a prerequisite for the
permission action when both are needed, but the plan orders them by family
(permission before immutable) because the runbook operator is expected to know
to apply immutable clearance first at runtime.

### I.6 Why the fixture-perms action comes last

The fixture-perms action (Section 9, terminal) is emitted for every
workstation and comes last because it is the only action keyed off the
workstation's workload rather than off any of the compliance fields. Placing
it last makes the plan easy to scan; any reviewer who wants to check the
fixture assignment can look at the terminal action of the plan and read the
workload directly out of the path.

## Appendix J -- Worked examples

### J.1 Worked example: fully compliant workstation

A hypothetical fully-compliant workstation would have `ptrace_scope=0`,
`core_pattern=core`, `suid_dumpable=2`, `coredump_conf=true`,
`in_debug_group=true`, `in_media_group=true`, `core_soft=unlimited`,
`core_hard=unlimited`, `scratch_perms=2770`, `scratch_owner=mediauser`,
`scratch_group=media`, and `scratch_immutable=false`. Its plan would contain a
single action:
`fixture-perms:/app/fixtures/<workload>/sample.<workload>:0644`. No
workstation in the current inventory is fully compliant; the closest is ws-003
which is compliant on nine of the ten families and requires only the
fs.suid_dumpable remediation plus the terminal fixture-perms action.

### J.2 Worked example: worst-case workstation

A hypothetical worst-case workstation would fail every family:
`ptrace_scope=3`, `core_pattern=|/bin/false`, `suid_dumpable=0`,
`coredump_conf=false`, `in_debug_group=false`, `in_media_group=false`,
`core_soft=0`, `core_hard=0`, `scratch_perms=0755`, `scratch_owner=root`,
`scratch_group=root`, `scratch_immutable=true`. Its plan would contain all ten
action families in the order documented in Section 10: three sysctl actions,
one systemd drop-in action, two group-add actions, one ulimit action, one
permission action, one fsattr action, and one fixture-perms action, for a
total of ten actions. No workstation in the current inventory is worst-case;
the closest are ws-001, ws-004, and ws-007, all of which require seven of the
ten families.

### J.3 Worked example: ws-005 walkthrough

ws-005 is a representative mid-severity workstation. Its state is:
`ptrace_scope=1`, `core_pattern=|/bin/false`, `suid_dumpable=2`,
`coredump_conf=true`, `in_debug_group=true`, `in_media_group=true`,
`core_soft=0`, `core_hard=0`, `scratch_perms=2770`, `scratch_owner=mediauser`,
`scratch_group=media`, `scratch_immutable=false`, `workload=png`. Its plan
therefore emits: 1) `sysctl:kernel.yama.ptrace_scope=0` because ptrace_scope
is not 0; 2) `sysctl:kernel.core_pattern=core` because the pattern is
`|/bin/false`; 3) no `sysctl:fs.suid_dumpable=2` because it is already 2; 4)
no systemd drop-in because the conf is present; 5) no group-add actions
because both memberships are present; 6) `ulimit:core:unlimited` because both
soft and hard are 0; 7) no permission action because the scratch directory is
compliant; 8) no fsattr action because immutable is false; 9) the terminal
`fixture-perms:/app/fixtures/png/sample.png:0644`. Total: four actions.

### J.4 Worked example: ws-006 walkthrough

ws-006 is the only workstation with the immutable attribute set on the scratch
directory, so it exercises the fsattr action that no other workstation in the
current inventory exercises. Its state is: `ptrace_scope=2`,
`core_pattern=core`, `suid_dumpable=0`, `coredump_conf=false`,
`in_debug_group=true`, `in_media_group=true`, `core_soft=unlimited`,
`core_hard=unlimited`, `scratch_perms=0777`, `scratch_owner=mediauser`,
`scratch_group=media`, `scratch_immutable=true`, `workload=mp4`. Its plan
therefore emits: 1) `sysctl:kernel.yama.ptrace_scope=0`; 2) no core_pattern
action; 3) `sysctl:fs.suid_dumpable=2`; 4)
`systemd:/etc/systemd/coredump.conf.d/media.conf`; 5) no debug-group action;
6) no media-group action; 7) no ulimit action; 8)
`perms:/var/lib/media/scratch:2770:mediauser:media` because the mode is 0777
(not 2770); 9) `fsattr:-i:/var/lib/media/scratch` because immutable is true;
10) `fixture-perms:/app/fixtures/mp4/sample.mp4:0644`. Total: six actions.

## Appendix K -- Reviewer walkthrough

### K.1 What the reviewer expects to see

A passing submission consists of a single Rego file (or a small set of Rego
files) under `/app/policy/` that declares the appropriate package and defines
the `actions` rule. The reviewer will run the harness sweep script against the
ten workstations in the DuckDB and expects the emitted plan for each
workstation to match the corresponding golden plan JSON exactly. Any mismatch
on any workstation is a failing submission.

### K.2 What the reviewer will not accept

The reviewer will not accept a submission that shells out to Python or Bash
from within the Rego file (Rego does not permit this, so a submission that
attempts it will fail at OPA parse time anyway). The reviewer will not accept
a submission that hard-codes the golden output as a lookup table keyed by
workstation ID; the Rego library must derive the plan from the input facts.
The reviewer will not accept a submission that reads directly from the DuckDB
or from the golden files; the only input is `input.workstation` as passed by
the harness.

### K.3 What the reviewer considers idiomatic

The reviewer considers idiomatic Rego to be a package declaration followed by
a series of helper rules that each produce a partial action string (either the
string itself or an empty list) and a terminal `actions` rule that
concatenates the partials in the canonical order. The reviewer will also
accept a monolithic `actions` rule built as a single array comprehension over
an internal decision table, provided the decision table encodes the same
conditions as the individual sections and the concatenation preserves the
canonical order.

### K.4 What the reviewer will run

The reviewer will run `bash /app/harness/sweep.sh check` from within the
container at /app. The check subcommand iterates over every workstation ID,
runs the loader and policy, and compares the emitted plan to the golden plan
via `harness/diff_plan.py`. Exit code 0 indicates a passing submission; any
other exit code indicates a failure, with the failing workstation IDs and the
diff details printed to stderr.

### K.5 What the reviewer will document in the case of a failure

In the case of a failure, the reviewer will record the workstation ID that
failed, the diff between the emitted and golden plans, and a one-line
diagnosis of the failure cause (usually one of: missing action for a family
the workstation triggers, extra action for a family the workstation does not
trigger, wrong ordering, or wrong literal string). The submitter is expected
to iterate on the Rego library until every workstation's plan matches.



## Per-workstation sweep-day transcript reconstructions

The following ten sections reconstruct the sweep-day session for each
workstation. The transcripts are provided so that a future engineer can see
how the sweep was conducted and can compare their own diagnostic-session flow
to the sweep flow. The transcripts do not introduce any new decision-matrix
rules; every rule is stated in Sections 3 through 9 of the postmortem body.

### WS-001 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-001 (render-a01). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-a01. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-001 was `tiff`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-001 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-001 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-001.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

### WS-002 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-002 (render-a02). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-a02. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-002 was `png`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-002 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-002 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-002.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

### WS-003 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-003 (render-a03). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-a03. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-003 was `mp4`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-003 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-003 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-003.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

### WS-004 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-004 (render-b01). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-b01. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-004 was `tiff`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-004 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-004 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-004.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

### WS-005 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-005 (render-b02). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-b02. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-005 was `png`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-005 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-005 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-005.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

### WS-006 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-006 (render-b03). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-b03. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-006 was `mp4`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-006 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-006 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-006.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

### WS-007 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-007 (render-c01). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-c01. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-007 was `tiff`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-007 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-007 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-007.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

### WS-008 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-008 (render-c02). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-c02. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-008 was `png`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-008 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-008 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-008.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

### WS-009 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-009 (render-c03). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-c03. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-009 was `mp4`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-009 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-009 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-009.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

### WS-010 sweep-day transcript reconstruction

The following is a reconstructed transcript of the on-call engineer's
sweep-day session for ws-010 (render-d01). The transcript is presented as
prose rather than as a raw shell log because the original tmux buffers were
not preserved; the engineer's actions and observations are reconstructed from
the sweep tooling's audit log and from the engineer's post-sweep notes.

The engineer opened a tmux session on their local workstation and SSH'd to
render-d01. On login they were greeted with the standard lab motd, which
includes a reminder that the workstation is a diagnostic host and that all
activity is logged. They immediately switched to the mediauser account via
`sudo -u mediauser -i` and confirmed the current working directory was
`/var/lib/media/scratch`.

The first probe checked the current value of `kernel.yama.ptrace_scope` by
reading `/proc/sys/kernel/yama/ptrace_scope`. The value was recorded verbatim
in the sweep audit log and later exported to the DuckDB. The engineer did not
modify the value; the sweep is read-only.

The next probe checked the current value of `kernel.core_pattern`. Again the
value was recorded and not modified. If the value was `|/bin/false`, the
engineer noted in their post-sweep notes that the workstation would require
the Section 4 remediation. If the value was already `core`, the engineer noted
that the workstation was compliant on this family.

The subsequent probes checked `fs.suid_dumpable`, the presence of the
systemd-coredump drop-in at `/etc/systemd/coredump.conf.d/media.conf`, the
group memberships of `mediauser` (via `id mediauser`), the current RLIMIT_CORE
values (via `ulimit -c` and `ulimit -Hc`), the mode/owner/group of
`/var/lib/media/scratch` (via `stat -c '%a %U %G'`), and the
immutable-attribute status (via `lsattr -d`). Each observation was recorded
verbatim in the sweep audit log.

After the compliance probes, the engineer confirmed that the assigned fixture
workload for ws-010 was `tiff`. This was read from the operations dashboard
rather than from the workstation itself; the dashboard is the source of truth
for the assignment and the DuckDB is a materialised copy of it.

The engineer closed the sweep session on ws-010 and moved to the next
workstation in the rotation. The full sweep of the ten workstations took
approximately seven hours, with the majority of the time spent on the initial
SSH setup and on the post-probe notes rather than on the probes themselves.

The sweep audit log for ws-010 was archived at
`/var/log/lab-sweeps/2026-02-11/ws-010.log` and is available for retrieval on
request. The archive is not shipped with the container image; the container
image ships only the derived DuckDB, the golden plan files, and the postmortem
itself.

## Appendix L -- Twelve-month chronological incident log

### L.1 Week of 2025-02-03

Debugging session on ws-002 discovered a spurious ptrace_scope reset that
turned out to be a stale unit dropping kernel.yama.ptrace_scope=1 at boot. The
drop-in file /etc/sysctl.d/60-hardening.conf was written by an unrelated
systems-engineering rollout and had gone unnoticed for four weeks. Sanchez
cleaned it up and filed IR-2025-01. The lab compliance owner opened a ticket
to add a periodic sweep for unexpected sysctl.d files; that ticket eventually
became the harness we ship today.

### L.2 Week of 2025-02-10

Follow-up sweep after IR-2025-01 confirmed that no other workstation carried
the stale drop-in. Okoro extended the sweep script to check `/etc/sysctl.d/`
and `/usr/lib/sysctl.d/` for any file naming a Yama key; today that check is
folded into the compliance scanner and out of scope for the Rego library.

### L.3 Week of 2025-02-17

First full end-to-end debugging session for the mp4 workload succeeded on
ws-003 after a two-week outage. Palmieri confirmed the reproducer works with
Valgrind attached and produces the expected use-after-free trace. The mp4
fixture size grew from 36 MiB to 48 MiB during this session as the codec team
added a worst-case sample; the golden hash was updated at the same time.

### L.4 Week of 2025-02-24

Coordinated maintenance window: all ten workstations received a kernel patch
(6.6.14 -> 6.6.16) to pick up a fix for an unrelated NVMe firmware quirk. The
maintenance ran clean; no compliance drift was observed post-patch.

### L.5 Week of 2025-03-03

Yoshida noted that ws-008 (Apple Silicon) was producing PNG core dumps that
gdb could not decode; the fix turned out to be a missing `debuginfod` cache
entry rather than a compliance issue. Filed as an operational note in the lab
wiki, out of scope for the Rego library.

### L.6 Week of 2025-03-10

The scratch directory on ws-004 filled to 100% after a runaway TIFF decoder
wrote 47 GB of intermediate output over a weekend. Bergstrom cleared the
directory and added a nightly cronjob to warn at 80% and page at 95%. The
cronjob is external to the Rego library.

### L.7 Week of 2025-03-17

First observation of the immutable-attribute-on-scratch issue on ws-005 (later
reverted). Hakim traced the attribute to a tamper-resistance experiment that
had not been properly gated by hostname. The reversion was pushed same-day.

### L.8 Week of 2025-03-24

Follow-up on the immutable-attribute experiment: the reversion was confirmed
successful on all workstations except render-b03 (ws-006). The lab operations
team opened a bug against the reversion script but did not push a fix until
the November refresh. This is the root cause of the current fs_immutable=true
value on ws-006.

### L.9 Week of 2025-03-31

Quarter-end audit surfaced that six workstations had drifted ulimit values;
Vasquez applied a fleet-wide reset. The reset was inlined into
`/etc/security/limits.conf` on three workstations against convention; those
inlines were dropped by the November refresh.

### L.10 Week of 2025-04-07

New on-call rotation started: added Nishimura. Nishimura spent the first week
shadowing Delacroix and did not perform any solo triage. No compliance drift
observed.

### L.11 Week of 2025-04-14

The TIFF decoder team pushed a change that improved the fixture reproducer
reliability from 70% to 95%. No compliance impact; the fixture file itself was
not updated.

### L.12 Week of 2025-04-21

First observed instance of the systemd-coredump storage overrun that later
became IR-2025-03. Petrov handled the immediate cleanup and opened the ticket
that eventually landed the MaxUse=40% override.

### L.13 Week of 2025-04-28

Sanchez and Okoro completed the media.conf drop-in rollout to all ten
workstations. This is the drop-in that the November refresh subsequently
removed.

### L.14 Week of 2025-05-05

Coordinated maintenance: dropped `kernel.msgmnb=131072` from the lab sysctl
overlay because the forecasting service that needed it had been
decommissioned. This is documented in Appendix A.2.

### L.15 Week of 2025-05-12

Weekly sweep found no drift. Uneventful week.

### L.16 Week of 2025-05-19

Weekly sweep found ws-007 had lost its media group membership; Palmieri
re-added it manually and filed IR-2025-02. That IR became the origin of the
group-membership check in the sweep.

### L.17 Week of 2025-05-26

Yoshida onboarded a new junior engineer; spent the week walking them through
the diagnostic workflow. No compliance drift.

### L.18 Week of 2025-06-02

Bergstrom identified a stale sysctl.d file on ws-009 (kernel.core_uses_pid=0)
that was preventing the mp4 reproducer from generating a usable core filename.
Removed the file and documented the case; the core_uses_pid sysctl is
explicitly out of scope for the Rego library (Section 5).

### L.19 Week of 2025-06-09

Hakim ran an experiment overriding kernel.core_pattern to
/var/lib/media/scratch/core-%p on ws-010; rolled back after the compliance
scanner flagged the value as unexpected. The lab convention of 'core' in the
working directory is the only supported value.

### L.20 Week of 2025-06-16

Weekly sweep found no drift.

### L.21 Week of 2025-06-23

Weekly sweep found the debug group missing on ws-004; Vasquez re-added it.
Same failure mode as IR-2025-02, different workstation.

### L.22 Week of 2025-06-30

Quarter-end audit surfaced no new issues.

### L.23 Week of 2025-07-07

Nishimura promoted to full on-call rotation after quarter's worth of
shadowing.

### L.24 Week of 2025-07-14

IR-2025-03 filed after the systemd-coredump storage overrun on ws-002. This is
the immediate origin of the MaxUse=40% override that Section 6 encodes.

### L.25 Week of 2025-07-21

Delacroix filed IR-2025-04 after observing that the TIFF fixture on ws-001 was
mode 0600 instead of 0644, preventing the mediauser account from reading it.
Manual fix same-day. This is the origin of the fixture-perms action documented
in Section 9's terminal paragraph.

### L.26 Week of 2025-07-28

Weekly sweep found no drift.

### L.27 Week of 2025-08-04

Maintenance window: kernel patched from 6.6.20 to 6.6.24. Clean run.

### L.28 Week of 2025-08-11

Weekly sweep found no drift.

### L.29 Week of 2025-08-18

Petrov noticed that ws-007 was producing PNG core dumps in `/tmp/` instead of
the current directory; traced to a PAM drop-in that overrode `chdir` on login.
Removed the drop-in. Out of scope for the Rego library.

### L.30 Week of 2025-08-25

Sanchez ran a full audit of every workstation's sysctl posture and confirmed
consistency across the fleet. This was the last full audit before the November
refresh.

### L.31 Week of 2025-09-01

Weekly sweep found no drift. Uneventful week.

### L.32 Week of 2025-09-08

IR-2025-05 filed after ws-005 experienced a kernel panic during a heavy TIFF
decoder load; unrelated to compliance.

### L.33 Week of 2025-09-15

Weekly sweep found no drift.

### L.34 Week of 2025-09-22

Renamed render-b3 to render-b03 to standardise the hostname format across the
fleet. This rename is why the immutable-attribute-reversion script keyed off
the wrong hostname and missed ws-006 (see Appendix A.6 and IR-2025-10).

### L.35 Week of 2025-09-29

Quarter-end audit surfaced no new issues.

### L.36 Week of 2025-10-06

IR-2025-06 filed after ws-008 developed a PAM issue that prevented mediauser
from logging in. Unrelated to compliance.

### L.37 Week of 2025-10-13

Vasquez ran a preliminary check of the incoming November refresh image on
ws-010 in a staging capacity. The check surfaced the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), and the mediauser reinstallation (A.5). The lab compliance owner signed
off on the refresh contingent on a follow-up remediation postmortem, which is
this document.

### L.38 Week of 2025-10-20

IR-2025-07 filed after a full sweep of the pre-refresh fleet confirmed the
compliance posture. Baseline captured for comparison with post-refresh state.

### L.39 Week of 2025-10-27

IR-2025-08 filed after Hakim discovered a leftover kernel.dmesg_restrict=1
sysctl on ws-002 that no one recalled adding. Removed the drop-in. The
dmesg_restrict sysctl is out of scope for the Rego library (Section 11).

### L.40 Week of 2025-11-03

The November refresh was pushed to the whole fleet over a coordinated
maintenance window. The refresh completed on every workstation without any
process-level failures.

### L.41 Week of 2025-11-10

First post-refresh sweep. The sweep surfaced the wide-fleet ptrace_scope
regression that ultimately led to this postmortem. Sanchez opened the parent
incident ticket.

### L.42 Week of 2025-11-17

Nishimura attempted to attach Valgrind to a TIFF reproducer on ws-001 and
received PTRACE_ATTACH: Operation not permitted. This is the first reported
user-facing symptom of the regression.

### L.43 Week of 2025-11-24

Delacroix repeated Nishimura's session on ws-004 and observed the same
failure. The two independent observations confirmed that the regression was
fleet-wide rather than per-host.

### L.44 Week of 2025-12-01

The lab compliance owner formally scoped the remediation postmortem. Draft
outline circulated to the on-call rotation for review.

### L.45 Week of 2025-12-08

Draft postmortem circulated. First round of review surfaced that the
immutable-attribute case on ws-006 was still unresolved; the section on
scratch-directory permissions was extended to cover it (this is Section 9's
paragraph on the fsattr action).

### L.46 Week of 2025-12-15

Second round of review. Petrov flagged that the fixture-perms action was not
adequately motivated in the draft; the section was rewritten to make the
deterministic-emit rationale explicit.

### L.47 Week of 2025-12-22

Third round of review. Yoshida and Bergstrom worked out the canonical action
ordering in Section 10; no further changes to the individual sections.

### L.48 Week of 2025-12-29

Fourth round of review. Sanchez signed off on the operational review sections
(Section 11 and the appendices).

### L.49 Week of 2026-01-05

Postmortem approved. Sweep tooling handed off to the on-call rotation.

### L.50 Week of 2026-01-12

First rotation-run sweep in production. Hakim on call, no drift observed.

### L.51 Week of 2026-01-19

First reproducer-blocked-by-Yama complaint from an outside team; on-call
escalated to lab compliance owner who confirmed the ptrace_scope remediation
is the correct fix.

### L.52 Week of 2026-01-26

Vasquez ran the first full round of the harness on ws-001 with a candidate
Rego library; the plan matched the golden output. First successful end-to-end
validation of the harness.

### L.53 Week of 2026-02-02

IR-2026-01 opened after an outside team reported that the compliance scanner
was producing false-positive warnings on the mp4 fixture. Root cause was a
stale golden hash, fixed same-day. Not a Rego library issue.

### L.54 Week of 2026-02-09

Preparation for the 2026-02-11 sweep: Sanchez confirmed every workstation was
accessible and that the inventory DuckDB was in a consistent state.

### L.55 Week of 2026-02-11

The sweep this postmortem is derived from. All ten workstations were swept
between 09:00 UTC and 16:00 UTC. Every observation recorded in this postmortem
was captured during this sweep. The subsequent per-workstation triage notes
and deep-dives are grounded in the sweep-day observations.

### L.56 Week of 2026-02-18

First week after the sweep. No new drift observed. The postmortem is finalised
and this document is released to the on-call rotation as the authoritative
reference.

## Appendix M -- Chip family and kernel matrix quirks

### M.1 Intel family (Rack A, kernel 6.6.32)

The Intel family uses Xeon Silver 4210 processors with 128 GB of RAM each. The
6.6.32 kernel is the current Debian Bookworm-backports LTS kernel for x86_64.
The Intel workstations do not have any per-chip quirks that affect the
compliance posture; the Yama, coredump, and ulimit behavior is identical to a
stock Bookworm install. The fixture workloads that run on the Intel family are
TIFF (three workstations: ws-001, ws-004 is actually AMD, ws-010) and PNG (one
workstation: ws-002); no MP4 workstation is currently on the Intel family.

### M.2 AMD family (Rack B, kernel 6.6.31)

The AMD family uses EPYC 7313P processors with 128 GB of RAM each. The 6.6.31
kernel is one patch behind the Intel family's 6.6.32; the kernel team defers
the AMD upgrade by one week to catch any AMD-specific regressions. The AMD
workstations have a known quirk where the core_pattern must not include the
`%c` conversion specifier (which the lab does not use anyway) because of a
misinterpretation in the Debian package's coredump handler. The AMD family
runs TIFF (ws-004), PNG (ws-005), and MP4 (ws-006).

### M.3 Apple Silicon family (Rack C, kernel 6.7.4)

The Apple Silicon family uses Apple M2 Ultra chips (running in a custom
rack-mount chassis) with 96 GB of unified memory each. The 6.7.4 kernel is a
downstream kernel with additional patches for Apple Silicon support; the
patches are contributed by the Asahi Linux project. The Apple Silicon
workstations have a quirk where the systemd-coredump handler must be
recompiled to link against the downstream libc; this is handled at image build
time and does not affect the Rego library. The Apple Silicon family runs TIFF
(ws-007), PNG (ws-008), and MP4 (ws-009).

### M.4 Kernel-version-dependent behavior

None of the compliance-related sysctls behave differently between 6.6.31,
6.6.32, and 6.7.4. The Yama LSM, the coredump handler, and the
fs.suid_dumpable path are stable across these kernel versions. The Rego
library does not need to key any decision off the kernel version or the chip
family; the decision matrix is uniform across the fleet. If a future kernel
introduces a per-chip-family variant of the decision matrix, the postmortem
will be revised.

## Appendix N -- Cross-reference tables

### N.1 Section-to-action cross-reference

Section 3 maps to the action `sysctl:kernel.yama.ptrace_scope=0` emitted at
position 1. Section 4 maps to `sysctl:kernel.core_pattern=core` at position 2.
Section 5 maps to `sysctl:fs.suid_dumpable=2` at position 3. Section 6 maps to
`systemd:/etc/systemd/coredump.conf.d/media.conf` at position 4. Section 7
maps to `group:add:mediauser:debug` at position 5 and
`group:add:mediauser:media` at position 6. Section 8 maps to
`ulimit:core:unlimited` at position 7. Section 9 maps to
`perms:/var/lib/media/scratch:2770:mediauser:media` at position 8,
`fsattr:-i:/var/lib/media/scratch` at position 9, and
`fixture-perms:/app/fixtures/<workload>/sample.<workload>:0644` at position
10.

### N.2 Field-to-action cross-reference

The DuckDB field `ptrace_scope` gates the Section 3 action. `core_pattern`
gates Section 4. `suid_dumpable` gates Section 5. `coredump_conf` gates
Section 6. `in_debug_group` gates the first Section 7 action; `in_media_group`
gates the second. `core_soft` and `core_hard` together gate Section 8.
`scratch_perms`, `scratch_owner`, `scratch_group` together gate the first
Section 9 action; `scratch_immutable` gates the second Section 9 action.
`workload` gates the terminal fixture-perms action.

### N.3 Workstation-to-plan cross-reference

ws-001 emits seven actions (Sections 3, 4, 5, 6, 7-debug, 8, 9-perms,
fixture-perms). ws-002 emits five actions (Sections 3, 4, 5, 6,
fixture-perms). ws-003 emits two actions (Section 5, fixture-perms). ws-004
emits seven actions (Sections 4, 5, 6, 7-debug, 7-media, 8, 9-perms,
fixture-perms). ws-005 emits four actions (Sections 3, 4, 8, fixture-perms).
ws-006 emits six actions (Sections 3, 5, 6, 9-perms, 9-fsattr, fixture-perms).
ws-007 emits seven actions (Sections 3, 4, 5, 6, 7-debug, 8, fixture-perms).
ws-008 emits five actions (Sections 4, 5, 7-media, 8, fixture-perms). ws-009
emits four actions (Section 5, 9-perms, plus fixture-perms after compliance on
other fronts). ws-010 emits four actions (Sections 3, 4, 8, fixture-perms).

### N.4 Redundancy check

No action string appears more than once in any golden plan. If a submission's
Rego library produces a plan with a duplicated action, the plan will not match
the golden for the workstation and the harness will report the mismatch.
Duplicated actions are always a bug in the Rego library, never a legitimate
outcome of the decision matrix.

## Appendix O -- Sample Rego library sketch

### O.1 Recommended file layout

A minimal Rego library that reproduces the golden plans can be written as a
single file at `/app/policy/workstation.rego` declaring `package
workstation.plan` and defining an `actions` rule that concatenates conditional
partials for each family. Additional files under `/app/policy/` are permitted
and are all loaded by the harness at OPA invocation time; the harness passes
`-d /app/policy` and OPA loads every `.rego` file recursively.

### O.2 Recommended rule structure

The recommended structure is a single helper rule per family that returns a
single-element array when the family's condition is triggered and an empty
array otherwise, followed by an `actions` rule that concatenates the helpers
with `array.concat`. This pattern makes the ordering explicit and gives the
reviewer a one-to-one mapping between the source lines and the ten sections of
the postmortem.

### O.3 Input access patterns

The library should access input fields as `input.workstation.<field>`. Rego
treats missing fields as errors at evaluation time; the harness guarantees
that every field documented in Section 2 is present in every invocation, so
the library does not need to guard against missing fields.

### O.4 Testing the library outside the harness

During development, a solver can test the library by running `opa eval -d
/app/policy -i - 'data.workstation.plan.actions'` with a hand-authored JSON
facts document. This bypasses the loader and differ; the solver is responsible
for constructing the input in the same shape as the loader produces. The
recommended shortcut is to copy the loader's output for a specific workstation
and use it as the test input.

### O.5 Common pitfalls

The most common pitfall is producing the actions in the wrong order because
Rego's default array construction is unordered. Fixing this requires explicit
concatenation with `array.concat` rather than using a comprehension over a set
of rules. The second most common pitfall is emitting an extra action for a
workstation whose fields coincidentally match a family's trigger condition
without the family actually applying; this is usually caused by a type
coercion bug (e.g. comparing a string `"0"` to an integer `0`).

## Appendix P -- Extended on-call runbook

### P.1 Runbook overview

The runbook is a step-by-step procedure the on-call engineer follows when a
workstation needs remediation. The runbook is written for a workstation that
has failed the sweep with at least one non-terminal action in its plan. If the
sweep produces only the terminal fixture-perms action for the workstation, the
on-call engineer runs the fixture-perms action and re-runs the sweep to
confirm compliance.

### P.2 Step 1: SSH to the workstation

The on-call engineer SSHes to the workstation as their own account, then `sudo
-u mediauser -i` into the mediauser shell. All subsequent commands are run in
the mediauser shell unless explicitly noted.

### P.3 Step 2: apply sysctl actions

The three sysctl actions are applied through `sudo sysctl -w
kernel.yama.ptrace_scope=0`, `sudo sysctl -w kernel.core_pattern=core`, and
`sudo sysctl -w fs.suid_dumpable=2`. Each command is idempotent; a workstation
that already has the target value does not require the command but is not
harmed by it. The persisting drop-in at /etc/sysctl.d/50-lab.conf is
regenerated by a separate configuration-management pass that is out of scope
for this runbook.

### P.4 Step 3: apply systemd drop-in action

The drop-in is created at /etc/systemd/coredump.conf.d/media.conf with the
lab-approved content (ProcessSizeMax=2G, MaxUse=40%). The runbook then issues
`sudo systemctl daemon-reload`. The daemon-reload is required so that the new
drop-in is picked up by the running systemd-coredump instance.

### P.5 Step 4: apply group-membership actions

The two group-add actions are applied through `sudo usermod -aG debug
mediauser` and `sudo usermod -aG media mediauser`. Each command is idempotent.
The change takes effect on the next login for mediauser; the runbook
re-invokes `sudo -u mediauser -i` after the group changes to pick up the new
memberships.

### P.6 Step 5: apply ulimit action

The ulimit action is applied by editing /etc/security/limits.d/50-media.conf
to set both the soft and hard limits for RLIMIT_CORE to `unlimited` for the
mediauser account. The change takes effect on the next login for mediauser.

### P.7 Step 6: apply permission and immutable actions

If the workstation has the immutable attribute set (fsattr action in the
plan), the runbook first runs `sudo chattr -i /var/lib/media/scratch` to clear
the attribute. Then the runbook runs `sudo chown mediauser:media
/var/lib/media/scratch` and `sudo chmod 2770 /var/lib/media/scratch`. The
ordering is important: chattr first, then chown, then chmod.

### P.8 Step 7: apply fixture-perms action

The terminal fixture-perms action is applied through `sudo chmod 0644
/app/fixtures/<workload>/sample.<workload>` where <workload> is the
workstation's assigned workload. The action is applied on every workstation
regardless of the current mode of the fixture.

### P.9 Step 8: re-run the sweep

After applying all actions, the on-call engineer re-runs the sweep script
against the workstation. The expected outcome is that the new plan contains
only the terminal fixture-perms action. Any other outcome indicates that at
least one remediation step did not take effect; the on-call engineer diagnoses
the failure and re-applies the affected action.

### P.10 Step 9: run the synthetic Valgrind attach

As a final verification, the on-call engineer runs the synthetic Valgrind
attach against a canned reproducer. The reproducer is at
/opt/media-pipeline/reproducers/canned-<workload>.sh; the expected outcome is
a successful attach with a Valgrind memcheck trace printed to stdout. Any
failure at this step indicates that the workstation is not ready for on-call
use and the remediation must be revisited.

### P.11 Step 10: re-tag the workstation

Once the sweep and the Valgrind attach both succeed, the on-call engineer
re-tags the workstation as ready for on-call use in the lab operations
dashboard. The tag is picked up by the compliance scanner on the next run and
the workstation is removed from the pending-remediation queue.

## Appendix Q -- Escalation FAQ

### Q.1 What if the plan for a workstation cannot be produced?

The most common reason for a plan-production failure is a malformed Rego
library that fails to parse. The harness reports the parse error in stderr;
the on-call engineer forwards the error to the submitter. The compliance
scanner does not accept a workstation whose plan cannot be produced; the
workstation stays in the pending-remediation queue until the Rego library is
fixed.

### Q.2 What if a workstation has been added since the last postmortem?

The postmortem is authoritative for the ten workstations enumerated in Section
2. If a new workstation is added to the DuckDB, the Rego library will produce
a plan for it using the same decision matrix; the compliance owner will
hand-author a golden plan for the new workstation using the decision matrix in
Section 10 and commit it to /app/golden/. Between the addition of the new
workstation and the commit of its golden plan, the sweep will report a
mismatch and the on-call engineer treats the mismatch as expected.

### Q.3 What if a workstation has been removed from the fleet?

If a workstation is decommissioned, its row is deleted from the DuckDB and its
golden plan file is deleted from /app/golden/. The sweep no longer processes
the decommissioned workstation. The Rego library is not affected.

### Q.4 What if the DuckDB is temporarily unavailable?

The sweep fails with exit code 3 if the DuckDB cannot be opened. The on-call
engineer investigates the DuckDB state and either restores from backup or
rebuilds from the CSV via harness/build_inventory.py. The Rego library is not
affected.

### Q.5 What if OPA is temporarily unavailable?

OPA is a static binary shipped with the container image, so unavailability
would only occur if the container image is corrupt. The on-call engineer
rebuilds the container image. The Rego library is not affected.

### Q.6 What if a golden plan file is corrupted?

The sweep will report a mismatch for the workstation whose golden plan is
corrupted. The on-call engineer either restores from the commit history or
hand-authors the golden plan using the decision matrix in Section 10.



## Per-workstation projected remediation timelines

The following ten sections project the remediation timeline for each
workstation based on the per-family cost estimates in Appendix P. The
projections are intended to help the on-call engineer plan their shift and to
give the compliance owner a sense of the total effort required to bring the
fleet back into compliance.

### WS-001 projected remediation timeline

The projected remediation timeline for ws-001 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-001 requires remediation on 6 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- ptrace_scope: 1 min

- core_pattern: 1 min

- systemd drop-in: 2 min

- debug group: 1 min

- ulimit: 2 min

- scratch perms: 2 min

Total projected time for ws-001: approximately 13 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-001 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-001 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.

### WS-002 projected remediation timeline

The projected remediation timeline for ws-002 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-002 requires remediation on 4 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- ptrace_scope: 1 min

- core_pattern: 1 min

- systemd drop-in: 2 min

- ulimit: 2 min

Total projected time for ws-002: approximately 10 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-002 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-002 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.

### WS-003 projected remediation timeline

The projected remediation timeline for ws-003 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-003 requires remediation on 1 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- suid_dumpable: 1 min

Total projected time for ws-003: approximately 5 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-003 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-003 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.

### WS-004 projected remediation timeline

The projected remediation timeline for ws-004 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-004 requires remediation on 6 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- ptrace_scope: 1 min

- systemd drop-in: 2 min

- debug group: 1 min

- media group: 1 min

- ulimit: 2 min

- scratch perms: 2 min

Total projected time for ws-004: approximately 13 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-004 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-004 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.

### WS-005 projected remediation timeline

The projected remediation timeline for ws-005 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-005 requires remediation on 3 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- ptrace_scope: 1 min

- core_pattern: 1 min

- ulimit: 2 min

Total projected time for ws-005: approximately 8 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-005 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-005 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.

### WS-006 projected remediation timeline

The projected remediation timeline for ws-006 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-006 requires remediation on 5 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- ptrace_scope: 1 min

- suid_dumpable: 1 min

- systemd drop-in: 2 min

- scratch perms: 2 min

- scratch immutable: 1 min

Total projected time for ws-006: approximately 11 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-006 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-006 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.

### WS-007 projected remediation timeline

The projected remediation timeline for ws-007 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-007 requires remediation on 6 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- ptrace_scope: 1 min

- core_pattern: 1 min

- systemd drop-in: 2 min

- debug group: 1 min

- ulimit: 2 min

- scratch perms: 2 min

Total projected time for ws-007: approximately 13 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-007 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-007 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.

### WS-008 projected remediation timeline

The projected remediation timeline for ws-008 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-008 requires remediation on 4 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- ptrace_scope: 1 min

- systemd drop-in: 2 min

- media group: 1 min

- ulimit: 2 min

Total projected time for ws-008: approximately 10 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-008 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-008 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.

### WS-009 projected remediation timeline

The projected remediation timeline for ws-009 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-009 requires remediation on 3 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- core_pattern: 1 min

- suid_dumpable: 1 min

- scratch perms: 2 min

Total projected time for ws-009: approximately 8 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-009 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-009 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.

### WS-010 projected remediation timeline

The projected remediation timeline for ws-010 is based on the per-family cost
estimates recorded in the extended runbook (Appendix P). The estimates assume
the on-call engineer is already SSHed to the workstation and has switched to
the mediauser account; time to SSH is not included.

ws-010 requires remediation on 3 non-terminal family(ies) plus the terminal
fixture-perms action. The per-family cost breakdown is:

- ptrace_scope: 1 min

- systemd drop-in: 2 min

- ulimit: 2 min

Total projected time for ws-010: approximately 9 minutes including the
terminal fixture-perms action, the sweep re-run to confirm compliance, the
synthetic Valgrind attach to verify the diagnostic workflow, and the
operational dashboard re-tag. The estimate has a plus-or-minus twenty percent
margin depending on how quickly the on-call engineer navigates between
commands.

The remediation is designed to be a single-session activity. There is no
expectation that the on-call engineer will need to come back to ws-010 on a
subsequent shift; every step in the runbook is fire-and-forget once applied.
If the sweep re-run after remediation produces a non-terminal action, the
on-call engineer diagnoses the failure of that step and re-applies it in the
same session.

Post-remediation, ws-010 is expected to remain in full compliance until the
next major image refresh, which is not currently scheduled. The weekly sweep
will confirm continued compliance.



## Per-workstation future-state simulations

The following ten sections simulate the steady-state behavior of each
workstation after the remediation is applied. The simulations are provided so
that a reviewer can understand what success looks like for each workstation
and can compare the post-remediation posture to the pre-remediation
observations.

### WS-001 future-state simulation

After the remediation is applied, ws-001 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a
TIFF reproducer without encountering the PTRACE_ATTACH: Operation not
permitted error, produce a core dump on demand, and copy the core dump to the
scratch directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-001, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-001 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-001 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

### WS-002 future-state simulation

After the remediation is applied, ws-002 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a PNG
reproducer without encountering the PTRACE_ATTACH: Operation not permitted
error, produce a core dump on demand, and copy the core dump to the scratch
directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-002, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-002 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-002 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

### WS-003 future-state simulation

After the remediation is applied, ws-003 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a MP4
reproducer without encountering the PTRACE_ATTACH: Operation not permitted
error, produce a core dump on demand, and copy the core dump to the scratch
directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-003, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-003 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-003 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

### WS-004 future-state simulation

After the remediation is applied, ws-004 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a
TIFF reproducer without encountering the PTRACE_ATTACH: Operation not
permitted error, produce a core dump on demand, and copy the core dump to the
scratch directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-004, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-004 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-004 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

### WS-005 future-state simulation

After the remediation is applied, ws-005 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a PNG
reproducer without encountering the PTRACE_ATTACH: Operation not permitted
error, produce a core dump on demand, and copy the core dump to the scratch
directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-005, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-005 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-005 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

### WS-006 future-state simulation

After the remediation is applied, ws-006 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a MP4
reproducer without encountering the PTRACE_ATTACH: Operation not permitted
error, produce a core dump on demand, and copy the core dump to the scratch
directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-006, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-006 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-006 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

### WS-007 future-state simulation

After the remediation is applied, ws-007 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a
TIFF reproducer without encountering the PTRACE_ATTACH: Operation not
permitted error, produce a core dump on demand, and copy the core dump to the
scratch directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-007, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-007 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-007 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

### WS-008 future-state simulation

After the remediation is applied, ws-008 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a PNG
reproducer without encountering the PTRACE_ATTACH: Operation not permitted
error, produce a core dump on demand, and copy the core dump to the scratch
directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-008, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-008 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-008 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

### WS-009 future-state simulation

After the remediation is applied, ws-009 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a MP4
reproducer without encountering the PTRACE_ATTACH: Operation not permitted
error, produce a core dump on demand, and copy the core dump to the scratch
directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-009, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-009 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-009 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

### WS-010 future-state simulation

After the remediation is applied, ws-010 is expected to enter a steady state
where the sweep produces a plan containing only the terminal fixture-perms
action. In this steady state, an on-call engineer can attach Valgrind to a
TIFF reproducer without encountering the PTRACE_ATTACH: Operation not
permitted error, produce a core dump on demand, and copy the core dump to the
scratch directory for offline analysis.

The steady-state posture also permits gdb to attach to any running
mediauser-owned process on ws-010, which is required for the
interactive-debugger portion of the diagnostic workflow. The gdb attach
requires the same Yama relaxation as the Valgrind attach; the two workflows
share the ptrace_scope=0 remediation.

If the November refresh is repeated in the future without the lab-specific
overlay being reapplied, ws-010 is expected to regress to the same
non-compliant posture observed at sweep time. The Rego library and the harness
together detect the regression on the next sweep; the on-call engineer runs
the same remediation as documented in the runbook to restore compliance.

There is no scenario in the current fleet plan under which ws-010 would need a
materially different decision matrix than the one documented in Sections 3
through 9. If the media pipeline gains a new fixture format (for example WebP
or AV1) the fixture-perms action's path pattern would be extended and a new
workstation might be assigned that workload; the underlying decision matrix is
unchanged.

## Appendix R -- Compliance scanner change log

### R.1 Compliance scanner v1 (Q2 2024)

The first version of the compliance scanner was a Bash script invoked from a
Jenkins job every hour against every workstation in the fleet. It probed the
same fields the current DuckDB records but did not store the observations;
each run was standalone. The v1 scanner produced a plain-text report per
workstation that the on-call engineer of the day reviewed manually. The v1
scanner did not support declarative policy; every check was hardcoded in the
Bash script.

### R.2 Compliance scanner v2 (Q4 2024)

The v2 scanner replaced the Bash script with a Python program that wrote
observations to a Postgres database. The v2 scanner introduced the notion of a
golden posture per workstation and produced a diff report between the observed
posture and the golden. The v2 scanner still hardcoded the checks; the golden
posture was a static YAML document under version control.

### R.3 Compliance scanner v3 (Q2 2025)

The v3 scanner replaced Postgres with DuckDB (to simplify the container image
footprint) and replaced the static YAML golden posture with a per-workstation
golden JSON plan generated from a declarative policy. The declarative policy
at v3 was written in Python and was tightly coupled to the scanner; v3 was a
step toward separating the policy from the scanner but did not achieve it.

### R.4 Compliance scanner v4 (Q4 2025)

The v4 scanner is the current design and the one this postmortem supports. The
v4 scanner uses DuckDB for observation storage, invokes OPA as a subprocess
for policy evaluation, and treats the Rego library as the authoritative policy
definition. The v4 scanner is the first version where the policy is genuinely
external to the scanner; the scanner does not know what actions the policy
will emit and simply diffs the emitted plan against the on-disk golden. The
Rego library that the current submission authors is the v4 policy.

### R.5 Rationale for the OPA migration

OPA was chosen over alternative policy engines (Cedar, Sentinel, Kyverno)
because it is the industry-standard policy engine for infrastructure
compliance, has a well-documented CLI, is packaged as a single static binary,
and has broad familiarity across the on-call rotation. Rego is more verbose
than Sentinel and less expressive than Cedar for row-level access control, but
for the kind of decision-matrix work the diagnostic workstations require it is
the best fit.

### R.6 Anticipated v5 changes

The next major scanner revision (planned for Q3 2026) will add support for
per-workstation exception lists so that a workstation temporarily undergoing
hardware maintenance can be excluded from the sweep without deleting its
DuckDB row. The current v4 scanner does not support exceptions; every
workstation in the DuckDB is swept every time. The v5 changes are out of scope
for the Rego library documented in this postmortem.

## Appendix S -- Security review notes

### S.1 Threat model summary

The diagnostic workstations sit inside the lab network segment and are
reachable only from the on-call jumphost. They are not exposed to the public
internet. The threat model therefore focuses on insider threats (a malicious
or compromised on-call engineer) and on supply-chain threats (a compromised
base image or a compromised compliance scanner).

### S.2 Insider threat considerations

The compliance regressions the November refresh introduced also reduced the
surface an insider could exploit; the Rego library documented in this
postmortem selectively re-opens those surfaces. Specifically: relaxing Yama to
level 0 permits an on-call engineer to attach a debugger to any process they
own, which is required for the diagnostic workflow but which also permits
reading arbitrary memory in those processes. This is an accepted risk
documented in the lab charter.

### S.3 Supply-chain considerations

The base image is the canonical Python 3.13 slim-Bookworm image with a SHA256
digest pin. The OPA binary is fetched from the official OpenPolicyAgent
release channel at build time. Neither dependency is under lab control; if
either is compromised, the compliance scanner is likely compromised as well.
The lab accepts this risk because the alternative (mirroring the entire
dependency graph) is prohibitively expensive for a ten-workstation fleet.

### S.4 Rego library review considerations

The Rego library itself is a small piece of infrastructure and is reviewed at
every commit. The library does not have access to any external data source;
the input.workstation object is the only input it sees. There is no plausible
way for the library to exfiltrate data or to modify state outside its own
return value. The library is therefore treated as low-risk from a supply-chain
perspective.

### S.5 Audit logging

Every sweep run is logged to /var/log/lab-sweeps/YYYY-MM-DD/. Every
remediation the on-call engineer applies is logged by the shell's audit
subsystem to /var/log/audit/audit.log. The two logs together provide a
complete trail of what was observed and what was changed. The Rego library
does not itself generate audit logs; the OPA invocation's stdout and stderr
are captured by the harness and written to the sweep run's log directory.

## Appendix T -- Glossary

### T.1 Yama

The Yama Linux Security Module. Enforces process-scoped ptrace restrictions
via `kernel.yama.ptrace_scope`. Documented in the kernel source at
Documentation/admin-guide/LSM/Yama.rst.

### T.2 systemd-coredump

A systemd service that intercepts kernel core dumps and stores them under
/var/lib/systemd/coredump/. Configurable via drop-in files under
/etc/systemd/coredump.conf.d/. Documented in the systemd manual page
systemd-coredump(8).

### T.3 RLIMIT_CORE

The POSIX process limit that caps the size of a core file. Managed via
getrlimit(2)/setrlimit(2) and via PAM limits.d for login sessions. The lab
requires RLIMIT_CORE=unlimited for mediauser on every diagnostic workstation.

### T.4 setgid bit

The mode bit (04000 in Unix octal notation, expressed as the leading 2 in the
four-digit mode 2770) that causes files created inside a directory to inherit
the directory's group ownership. The lab requires the setgid bit on
/var/lib/media/scratch to ensure coredumps inherit the media group.

### T.5 chattr +i

The Linux file-attribute flag (`immutable`) that prevents any modification of
a file or directory, including permission changes. Managed via `chattr` and
inspected via `lsattr`. The lab does not use +i on the scratch directory in
the target posture; the current presence on ws-006 is a documented reversion
miss.

### T.6 mediauser

The account on every diagnostic workstation that runs the diagnostic
reproducers. Must be a member of the `debug` and `media` groups. UID and GID
are stable across the fleet but are not encoded in this postmortem because
they are irrelevant to the decision matrix.

### T.7 media group

The group that owns /var/lib/media/scratch. Members are permitted to write to
the scratch directory and to read files created there.

### T.8 debug group

The group that grants read access to /var/lib/systemd/coredump/. Members are
permitted to read coredumps produced by any process on the workstation.

### T.9 sweep

A one-shot execution of the compliance scanner across the whole workstation
fleet. The lab runs weekly sweeps on Monday and on-demand sweeps as needed.

### T.10 plan

The ordered list of remediation action strings produced by the Rego library
for a specific workstation. The plan is the authoritative document that the
on-call engineer applies during remediation.

### T.11 golden

The on-disk expected plan for a workstation, committed to /app/golden/. The
compliance scanner compares the plan emitted by the Rego library to the golden
and reports a mismatch if they differ.

### T.12 harness

The set of scripts under /app/harness/ that together implement the sweep.
Includes build_inventory.py (bootstraps the DuckDB), load_facts.py (projects a
workstation row to JSON), run_policy.sh (invokes OPA), and diff_plan.py
(compares emitted to golden).

### T.13 fixture

One of three sample media files (TIFF, PNG, MP4) that a diagnostic reproducer
processes. Fixtures are read-only reference material stored at
/app/fixtures/<workload>/sample.<workload>.

### T.14 workload

The fixture format assigned to a workstation (`tiff`, `png`, or `mp4`).
Recorded per workstation in the DuckDB. Determines the terminal fixture-perms
action in the plan.

### T.15 chip family

The processor family of a workstation (`intel`, `amd`, or `apple-silicon`).
Determines the physical rack and the kernel version but does not affect the
decision matrix.

### T.16 kernel release

The Linux kernel version running on a workstation. Currently 6.6.31 or 6.6.32
on x86_64 and 6.7.4 on Apple Silicon. Documented per workstation in the
DuckDB.

### T.17 canonical action string

The exact literal string that must appear in the plan for a given remediation
family. Documented per family in Sections 3 through 9. Deviations (case,
whitespace, punctuation, spelling) are treated as different actions by the
compliance scanner.

### T.18 emission order

The order in which the plan lists its constituent actions. Documented in
Section 10. Deviations are treated as mismatches by the compliance scanner.

### T.19 application order

The order in which the on-call engineer applies the plan's actions during
remediation. Documented in the extended runbook in Appendix P. May differ from
the emission order (specifically, chattr -i is applied before chmod even
though the plan emits the chmod action first).

### T.20 diagnostic session

A time-boxed activity during which an on-call engineer attaches gdb or
Valgrind to a media pipeline process to reproduce and diagnose a bug. The
diagnostic session is the entire raison d'etre of the diagnostic workstation
fleet; every compliance decision serves the session.



## Appendix U -- Extended per-family design rationale

This appendix documents the design rationale for each remediation family in
more depth than the main postmortem sections. The material is provided for
reviewers who want to understand not only what the Rego library must produce
but also why the lab has chosen each specific action string and each specific
ordering constraint. Nothing in this appendix changes the decision matrix;
every rule in Sections 3 through 9 remains authoritative.

### U.1 The Yama ptrace_scope family

The Yama Linux Security Module was introduced in kernel 3.4 to give
distributions a way to enforce ptrace restrictions that Linux capabilities
alone cannot express. On Debian Bookworm the default value is 1, which
restricts ptrace to a parent process only; this is the value that blocks
Valgrind attach for the diagnostic workflow. Relaxing to 0 permits ptrace
across parent boundaries within the same UID, which is exactly what Valgrind
and gdb need when attached from a fresh shell. The alternative would be to use
the CAP_SYS_PTRACE capability, but that requires either setuid on Valgrind,
which is dangerous, or a per-invocation capability grant, which is fragile.
The lab chose the Yama relaxation because it is the simplest reversible
change; setting the sysctl back to 1 restores the Bookworm default posture
immediately.

### U.2 The core_pattern family

The kernel.core_pattern sysctl controls where a crashing process writes its
core file. Since Debian 12 the default has been the pipe form pointing to
/bin/false, which discards the core entirely. On a diagnostic host that
discard defeats the entire post-mortem inspection workflow, so the lab
requires the value core, which writes the core to a file named core in the
current working directory. The lab considered several alternative patterns
(absolute paths, pid-suffixed patterns, systemd-coredump handler strings) and
rejected each of them: absolute paths conflict with the scratch directory
convention, pid suffixes complicate the naming convention the on-call runbook
relies on, and the systemd-coredump handler duplicates work already done by
the coredump drop-in from Section 6. The literal string core is the minimum
viable value.

### U.3 The suid_dumpable family

The fs.suid_dumpable sysctl controls whether set-user-id executables produce a
core dump on crash. On a general-purpose Debian host the value is 0 which
disables the behavior to prevent an attacker from harvesting secrets from a
suid binary. On a diagnostic host the value must be 2 which enables it with
root-owned mode-derived permissions so that the on-call engineer can inspect a
core dump from the GPU shim. Value 1 is technically also permissive but
produces cores that only root can read; this is worse than either 0 or 2 for
the diagnostic workflow. The lab requires exactly 2.

### U.4 The systemd-coredump drop-in family

The systemd-coredump helper stores kernel core dumps under
/var/lib/systemd/coredump/. Its defaults set ProcessSizeMax to 2 GiB and
MaxUse to 10 percent of the containing device, which are sensible for a shared
multi-tenant host but too restrictive for a diagnostic host that occasionally
produces multi-GB cores. The lab drop-in raises ProcessSizeMax to 2 GiB (which
matches the default but the drop-in exists to hold the file open against
future default changes) and MaxUse to 40 percent. The drop-in filename
media.conf is a lab convention; the compliance scanner keys off the filename
because inspecting the content of every drop-in fleet-wide is impractical.

### U.5 The mediauser group family

The mediauser account must be a member of two groups: debug for coredump read
access, media for scratch directory write access. Neither membership is
granted by default when the account is reprovisioned; the November refresh
script does not restore either. The Rego library emits two separate group-add
actions rather than a single bundled group action because the on-call runbook
applies each usermod invocation separately, and because the compliance scanner
audits each membership separately.

### U.6 The ulimit family

The RLIMIT_CORE limit must be unlimited on the diagnostic workstations because
a bounded limit truncates cores that exceed the bound. On a 32 GiB fixture
reproducer a bounded 4096 KiB limit would produce a 4 MiB core file that
contains only the first few pages of the process address space; that core is
useless for debugging. The lab requires both soft and hard limits to be
unlimited so that even a compromised login shell cannot lower the effective
limit before triggering the reproducer.

### U.7 The scratch permissions family

The scratch directory /var/lib/media/scratch is the working directory for
diagnostic reproducers. Its target posture is mode 2770 owned by
mediauser:media. The setgid bit (the leading 2 in 2770) is the load-bearing
detail: without it, files created inside the directory inherit the primary
group of the creating account, which for mediauser is the mediauser group.
Coredumps left in the scratch directory would then be readable only by the
mediauser account, not by the rest of the on-call rotation. The setgid bit
forces group inheritance so every member of the media group can read and clean
up left-behind files.

### U.8 The immutable-attribute family

The immutable attribute prevents any modification of a file or directory,
including permission changes. On a diagnostic host the attribute must not be
set on the scratch directory because it blocks the runbook operator from
applying the Section 9 permission action. The current presence of the
attribute on ws-006 is a documented reversion miss from IR-2025-10; the Rego
library emits the chattr clearance action to correct it. Once cleared, the
attribute is not expected to reappear on any workstation.

### U.9 The fixture-perms family

The fixture-perms action is the only always-emitted action in the plan. Its
purpose is twofold: first, to ensure the assigned fixture is readable by
mediauser regardless of any permission drift that may have occurred since the
last fixture-integrity sweep; second, to provide a deterministic terminal
action that proves the Rego library read the workstation workload assignment
and did not simply return an empty plan. The action is emitted for every
workstation, in every plan, keyed off the workstation workload field. The mode
0644 permits read for owner and group and other; this is intentionally
permissive because the fixtures are non-sensitive reference material.

### U.10 Cross-family interactions

The nine remediation families do not interact with each other except through
the sixth family, the immutable-attribute clearance, which is a prerequisite
for the fifth family, the scratch permission change. The Rego library does not
need to model the prerequisite relationship because the on-call runbook is
responsible for applying the actions in the correct operational order. The
Rego library only emits the actions in the canonical order documented in
Section 10.



## Appendix V -- Failure-mode taxonomy

This appendix enumerates the failure modes the compliance scanner has observed
on candidate Rego libraries. Each failure mode is described in enough detail
that a submitter can recognise it in their own submission and correct it
before running the full sweep. The failure modes are grouped by the root
cause; the submitter should read the failure descriptions before writing their
library, not after their submission has already failed.

### V.1 Wrong-order failures

The most common failure mode is emitting the actions in an order other than
the canonical order from Section 10. This usually happens because the
submitter used a set comprehension, which is unordered, to construct the
actions array. The fix is to use explicit array concatenation with
array.concat, ordering the concatenations to match Section 10.

### V.2 Missing-action failures

The second most common failure mode is failing to emit an action that the
golden plan requires. This usually happens because the submitter forgot to
check the corresponding field, or because the submitter compared a string to
an integer and got a false negative. The fix is to add the check and to use
Rego type coercion rules carefully.

### V.3 Extra-action failures

The third most common failure mode is emitting an action that the golden plan
does not require. This usually happens because the submitter interpreted a
field value too permissively. The fix is to tighten the comparison.

### V.4 Wrong-string failures

The fourth failure mode is emitting an action string that is close to but not
identical to the canonical string. Examples include trailing whitespace, wrong
capitalisation, or wrong path. The fix is to copy the canonical strings
verbatim from Sections 3 through 9.

### V.5 Duplicated-action failures

A rarer failure mode is emitting the same action twice. This usually happens
because the submitter has two helper rules that both trigger for the same
input. The fix is to consolidate the redundant helpers.

### V.6 Undefined-actions failures

The Rego library must define data.workstation.plan.actions as a concrete
array; if the rule is undefined for a specific input the harness fails with a
not-produced error. This usually happens because the submitter forgot to
handle a code path where every family condition is false; the fix is to define
the actions rule to fall through to the terminal fixture-perms action even
when no other family triggers.

### V.7 Type-error failures

Rego is strict about types; a submission that treats a string field as an
integer or vice versa fails at OPA evaluation time. This usually happens
because the DuckDB CSV loader parses ptrace_scope and suid_dumpable as
integers, ulimit_core_soft and ulimit_core_hard as strings, and the various
boolean fields as booleans, and the submitter forgets which is which. The fix
is to consult the v_workstation view schema and to match the Rego comparisons
to the declared types.

### V.8 Non-canonical-package failures

The harness expects the rule at data.workstation.plan.actions. A submission
that declares the package as workstation, or as workstation.rules, or as
media.plan, fails because the harness query path does not resolve. The fix is
to use the exact package declaration package workstation.plan.



## Appendix W -- Per-workstation regression walkthroughs

Each of the ten workstations experienced the November refresh differently. The
regression walkthroughs below reconstruct, for each workstation, the sequence
of refresh events that produced the observed sweep-day state. The walkthroughs
are provided as a diagnostic aid for the compliance owner and do not affect
the decision matrix; the Rego library must produce the correct plan for the
observed state regardless of how the state came to be.

### WS-001 regression walkthrough

The refresh on ws-001 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-001
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab kernel.yama.ptrace_scope=0 setting, leaving the workstation on the Bookworm default value 3.

- The sysctl overlay rebase dropped the lab kernel.core_pattern=core setting, leaving the workstation with the Bookworm default value |/bin/false.

- The coredump-drop-in removal (A.3) removed the media.conf drop-in from /etc/systemd/coredump.conf.d/. The workstation is now running with the stock systemd-coredump defaults.

- The mediauser reinstallation (A.5) reset the account group memberships to the default set; the debug group membership was not restored by the downstream lab-specific script.

- The PAM limits rewrite (A.4) dropped the inlined RLIMIT_CORE setting because it was inlined against convention. The current soft/hard limits are 0/0.

- The scratch directory rebootstrap (A.6) reset the directory to the fallback posture. Current state: mode 0770, owner root, group media.



The sum of these refresh outcomes on ws-001 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-001 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.

### WS-002 regression walkthrough

The refresh on ws-002 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-002
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab kernel.yama.ptrace_scope=0 setting, leaving the workstation on the Bookworm default value 1.

- The sysctl overlay rebase dropped the lab kernel.core_pattern=core setting, leaving the workstation with the Bookworm default value |/bin/false.

- The coredump-drop-in removal (A.3) removed the media.conf drop-in from /etc/systemd/coredump.conf.d/. The workstation is now running with the stock systemd-coredump defaults.

- The PAM limits rewrite (A.4) dropped the inlined RLIMIT_CORE setting because it was inlined against convention. The current soft/hard limits are 0/0.



The sum of these refresh outcomes on ws-002 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-002 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.

### WS-003 regression walkthrough

The refresh on ws-003 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-003
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab fs.suid_dumpable=2 setting, leaving the workstation with the Bookworm default value 1.



The sum of these refresh outcomes on ws-003 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-003 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.

### WS-004 regression walkthrough

The refresh on ws-004 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-004
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab kernel.yama.ptrace_scope=0 setting, leaving the workstation on the Bookworm default value 3.

- The coredump-drop-in removal (A.3) removed the media.conf drop-in from /etc/systemd/coredump.conf.d/. The workstation is now running with the stock systemd-coredump defaults.

- The mediauser reinstallation (A.5) reset the account group memberships to the default set; the debug group membership was not restored by the downstream lab-specific script.

- The mediauser reinstallation (A.5) similarly did not restore the media group membership on this workstation.

- The PAM limits rewrite (A.4) dropped the inlined RLIMIT_CORE setting because it was inlined against convention. The current soft/hard limits are 0/0.

- The scratch directory rebootstrap (A.6) reset the directory to the fallback posture. Current state: mode 0755, owner root, group root.



The sum of these refresh outcomes on ws-004 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-004 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.

### WS-005 regression walkthrough

The refresh on ws-005 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-005
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab kernel.yama.ptrace_scope=0 setting, leaving the workstation on the Bookworm default value 1.

- The sysctl overlay rebase dropped the lab kernel.core_pattern=core setting, leaving the workstation with the Bookworm default value |/bin/false.

- The PAM limits rewrite (A.4) dropped the inlined RLIMIT_CORE setting because it was inlined against convention. The current soft/hard limits are 0/0.



The sum of these refresh outcomes on ws-005 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-005 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.

### WS-006 regression walkthrough

The refresh on ws-006 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-006
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab kernel.yama.ptrace_scope=0 setting, leaving the workstation on the Bookworm default value 2.

- The sysctl overlay rebase dropped the lab fs.suid_dumpable=2 setting, leaving the workstation with the Bookworm default value 0.

- The coredump-drop-in removal (A.3) removed the media.conf drop-in from /etc/systemd/coredump.conf.d/. The workstation is now running with the stock systemd-coredump defaults.

- The scratch directory rebootstrap (A.6) reset the directory to the fallback posture. Current state: mode 0777, owner mediauser, group media.

- The scratch directory rebootstrap also applied the immutable attribute as part of the tamper-resistance experiment; this attribute was not reverted because the reversion script keyed off the wrong hostname (see IR-2025-10).



The sum of these refresh outcomes on ws-006 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-006 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.

### WS-007 regression walkthrough

The refresh on ws-007 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-007
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab kernel.yama.ptrace_scope=0 setting, leaving the workstation on the Bookworm default value 3.

- The sysctl overlay rebase dropped the lab kernel.core_pattern=core setting, leaving the workstation with the Bookworm default value |/bin/false.

- The coredump-drop-in removal (A.3) removed the media.conf drop-in from /etc/systemd/coredump.conf.d/. The workstation is now running with the stock systemd-coredump defaults.

- The mediauser reinstallation (A.5) reset the account group memberships to the default set; the debug group membership was not restored by the downstream lab-specific script.

- The PAM limits rewrite (A.4) dropped the inlined RLIMIT_CORE setting because it was inlined against convention. The current soft/hard limits are 0/0.

- The scratch directory rebootstrap (A.6) reset the directory to the fallback posture. Current state: mode 0770, owner mediauser, group media.



The sum of these refresh outcomes on ws-007 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-007 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.

### WS-008 regression walkthrough

The refresh on ws-008 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-008
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab kernel.yama.ptrace_scope=0 setting, leaving the workstation on the Bookworm default value 3.

- The coredump-drop-in removal (A.3) removed the media.conf drop-in from /etc/systemd/coredump.conf.d/. The workstation is now running with the stock systemd-coredump defaults.

- The mediauser reinstallation (A.5) similarly did not restore the media group membership on this workstation.

- The PAM limits rewrite (A.4) dropped the inlined RLIMIT_CORE setting because it was inlined against convention. The current soft/hard limits are 0/0.



The sum of these refresh outcomes on ws-008 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-008 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.

### WS-009 regression walkthrough

The refresh on ws-009 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-009
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab kernel.core_pattern=core setting, leaving the workstation with the Bookworm default value |/bin/false.

- The sysctl overlay rebase dropped the lab fs.suid_dumpable=2 setting, leaving the workstation with the Bookworm default value 0.

- The scratch directory rebootstrap (A.6) reset the directory to the fallback posture. Current state: mode 2775, owner mediauser, group media.



The sum of these refresh outcomes on ws-009 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-009 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.

### WS-010 regression walkthrough

The refresh on ws-010 completed on 2025-11-03 as part of the coordinated
fleet-wide maintenance. The refresh applied the sysctl overlay rebase
(Appendix A.2), the coredump-drop-in removal (A.3), the PAM limits rewrite
(A.4), the mediauser reinstallation (A.5), and the scratch directory
rebootstrap (A.6). The specific combination of refresh outcomes for ws-010
determined the sweep-day state and hence the remediation plan.



- The sysctl overlay rebase dropped the lab kernel.yama.ptrace_scope=0 setting, leaving the workstation on the Bookworm default value 1.

- The coredump-drop-in removal (A.3) removed the media.conf drop-in from /etc/systemd/coredump.conf.d/. The workstation is now running with the stock systemd-coredump defaults.

- The PAM limits rewrite (A.4) dropped the inlined RLIMIT_CORE setting because it was inlined against convention. The current soft/hard limits are 4096/4096.



The sum of these refresh outcomes on ws-010 produced the observed sweep-day
state and the corresponding remediation plan. A future refresh that preserves
each of the affected settings would leave ws-010 in a compliant post-refresh
state and the plan would collapse to only the terminal fixture-perms action.
The lab is working with the image team to that end but does not expect the
improvements to land before the next major refresh.



## Appendix X -- Closing remarks

This postmortem is the complete and authoritative reference for the compliance
regression on the image-rendering diagnostic workstation fleet. Every fact
required to produce a correct remediation plan for every workstation in the
current inventory is contained in Sections 3 through 10 of the main body. The
appendices provide historical context, engineering rationale, and operational
detail; they are not strictly required for a passing Rego library submission
but are provided so that the submitter can understand the design constraints
under which the decision matrix was defined.

The next scheduled revision of this postmortem is Q3 2026 or upon the next
major image refresh, whichever comes first. Between now and the next revision
the decision matrix is frozen; any change that would require updating the
matrix is escalated to the compliance owner for a postmortem revision rather
than being applied as an ad-hoc modification.



## Appendix Y -- Post-remediation verification records

The following ten sub-sections are the anticipated post-remediation
verification records for each workstation. Each record projects what the sweep
will emit after the remediation runbook has been applied and what the
synthetic Valgrind attach will produce. The records are forward-looking; they
document the expected state, not an observed state, and are provided as a
reference for the on-call engineer during the remediation session.

### WS-001 post-remediation verification

After the remediation runbook has been applied to ws-001, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/tiff/sample.tiff:0644`. The plan is the terminal
fixture-perms action for the TIFF workload; no other action should appear.

The synthetic Valgrind attach against the canned TIFF reproducer on ws-001 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-001 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-001 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-001 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-001 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-001 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-001 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-001 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-001 is removed from the pending-remediation queue.

### WS-002 post-remediation verification

After the remediation runbook has been applied to ws-002, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/png/sample.png:0644`. The plan is the terminal
fixture-perms action for the PNG workload; no other action should appear.

The synthetic Valgrind attach against the canned PNG reproducer on ws-002 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-002 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-002 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-002 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-002 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-002 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-002 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-002 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-002 is removed from the pending-remediation queue.

### WS-003 post-remediation verification

After the remediation runbook has been applied to ws-003, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/mp4/sample.mp4:0644`. The plan is the terminal
fixture-perms action for the MP4 workload; no other action should appear.

The synthetic Valgrind attach against the canned MP4 reproducer on ws-003 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-003 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-003 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-003 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-003 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-003 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-003 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-003 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-003 is removed from the pending-remediation queue.

### WS-004 post-remediation verification

After the remediation runbook has been applied to ws-004, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/tiff/sample.tiff:0644`. The plan is the terminal
fixture-perms action for the TIFF workload; no other action should appear.

The synthetic Valgrind attach against the canned TIFF reproducer on ws-004 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-004 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-004 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-004 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-004 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-004 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-004 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-004 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-004 is removed from the pending-remediation queue.

### WS-005 post-remediation verification

After the remediation runbook has been applied to ws-005, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/png/sample.png:0644`. The plan is the terminal
fixture-perms action for the PNG workload; no other action should appear.

The synthetic Valgrind attach against the canned PNG reproducer on ws-005 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-005 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-005 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-005 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-005 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-005 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-005 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-005 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-005 is removed from the pending-remediation queue.

### WS-006 post-remediation verification

After the remediation runbook has been applied to ws-006, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/mp4/sample.mp4:0644`. The plan is the terminal
fixture-perms action for the MP4 workload; no other action should appear.

The synthetic Valgrind attach against the canned MP4 reproducer on ws-006 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-006 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-006 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-006 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-006 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-006 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-006 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-006 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-006 is removed from the pending-remediation queue.

### WS-007 post-remediation verification

After the remediation runbook has been applied to ws-007, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/tiff/sample.tiff:0644`. The plan is the terminal
fixture-perms action for the TIFF workload; no other action should appear.

The synthetic Valgrind attach against the canned TIFF reproducer on ws-007 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-007 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-007 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-007 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-007 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-007 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-007 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-007 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-007 is removed from the pending-remediation queue.

### WS-008 post-remediation verification

After the remediation runbook has been applied to ws-008, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/png/sample.png:0644`. The plan is the terminal
fixture-perms action for the PNG workload; no other action should appear.

The synthetic Valgrind attach against the canned PNG reproducer on ws-008 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-008 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-008 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-008 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-008 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-008 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-008 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-008 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-008 is removed from the pending-remediation queue.

### WS-009 post-remediation verification

After the remediation runbook has been applied to ws-009, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/mp4/sample.mp4:0644`. The plan is the terminal
fixture-perms action for the MP4 workload; no other action should appear.

The synthetic Valgrind attach against the canned MP4 reproducer on ws-009 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-009 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-009 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-009 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-009 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-009 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-009 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-009 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-009 is removed from the pending-remediation queue.

### WS-010 post-remediation verification

After the remediation runbook has been applied to ws-010, the sweep is
expected to produce a plan containing exactly one action:
`fixture-perms:/app/fixtures/tiff/sample.tiff:0644`. The plan is the terminal
fixture-perms action for the TIFF workload; no other action should appear.

The synthetic Valgrind attach against the canned TIFF reproducer on ws-010 is
expected to succeed. The attach output begins with the Valgrind banner,
followed by the memcheck initialisation lines, followed by the reproducer
output interleaved with memcheck findings. A successful attach produces at
least one memcheck finding (the reproducer is designed to trigger one) and
terminates with a normal exit code from the reproducer, not from Valgrind.

The gdb attach against the canned reproducer on ws-010 is expected to succeed
as well. The attach produces the standard gdb prompt, the on-call engineer can
inspect the reproducer state, set breakpoints, and detach cleanly. A failed
gdb attach would print the same PTRACE_ATTACH: Operation not permitted error
that triggered the original regression; the post-remediation state should not
produce that error.

The scratch directory on ws-010 is expected to be writable by mediauser after
remediation. A test touch of a file in the scratch directory should succeed
and the resulting file should inherit the media group ownership from the
setgid bit. If either check fails, the remediation of the Section 9 permission
action was incomplete and the on-call engineer re-runs the chmod step.

The systemd-coredump service on ws-010 is expected to be running and to be
honouring the media.conf drop-in. The check is a systemctl status
systemd-coredump.socket followed by a synthetic segfault via kill -SEGV
against a test process; the resulting core file should appear under
/var/lib/systemd/coredump/ with a size below the ProcessSizeMax limit.

The mediauser group memberships on ws-010 are expected to include both debug
and media after remediation. The check is a fresh login as mediauser followed
by id mediauser; the output should list both groups. If either is missing the
on-call engineer re-runs the corresponding usermod step.

The RLIMIT_CORE values on ws-010 are expected to be unlimited for both the
soft and hard limits after remediation. The check is a fresh login as
mediauser followed by ulimit -c and ulimit -Hc; both should print the literal
string unlimited. If either does not, the PAM drop-in was not correctly
updated and the on-call engineer re-inspects
/etc/security/limits.d/50-media.conf.

The immutable attribute check on ws-010 is expected to return an unset
attribute. The check is lsattr -d /var/lib/media/scratch; the leading
attribute string should not include an i. If the attribute is still set the
on-call engineer re-runs chattr -i and re-verifies before proceeding.

After all verification steps succeed, the on-call engineer re-tags ws-010 as
ready for on-call use in the operations dashboard and confirms the tag via the
dashboard API. The tag change is picked up by the compliance scanner on the
next run and ws-010 is removed from the pending-remediation queue.



## Appendix Z -- Index of load-bearing strings

The following list enumerates every string that must appear verbatim in either
the Rego library or the emitted action strings. Deviations in any of these
strings cause the compliance scanner to reject the submission. The list is
exhaustive for the current inventory and should be consulted by the submitter
as a final proofreading step before running the sweep.

- **Package declaration**: `package workstation.plan`
- **Query path**: `data.workstation.plan.actions`
- **Yama action**: `sysctl:kernel.yama.ptrace_scope=0`
- **core_pattern action**: `sysctl:kernel.core_pattern=core`
- **suid_dumpable action**: `sysctl:fs.suid_dumpable=2`
- **systemd drop-in action**: `systemd:/etc/systemd/coredump.conf.d/media.conf`
- **debug group action**: `group:add:mediauser:debug`
- **media group action**: `group:add:mediauser:media`
- **ulimit action**: `ulimit:core:unlimited`
- **scratch permission action**: `perms:/var/lib/media/scratch:2770:mediauser:media`
- **scratch immutable clearance action**: `fsattr:-i:/var/lib/media/scratch`
- **TIFF fixture action**: `fixture-perms:/app/fixtures/tiff/sample.tiff:0644`
- **PNG fixture action**: `fixture-perms:/app/fixtures/png/sample.png:0644`
- **MP4 fixture action**: `fixture-perms:/app/fixtures/mp4/sample.mp4:0644`
- **DuckDB view name**: `v_workstation`
- **scratch directory path**: `/var/lib/media/scratch`
- **systemd drop-in path**: `/etc/systemd/coredump.conf.d/media.conf`
- **Golden plan filename pattern**: `plan_ws<NNN>.json`
- **Rego library base directory**: `/app/policy`
- **Harness runner script**: `/app/harness/run_policy.sh`
- **Facts loader script**: `/app/harness/load_facts.py`
- **Plan differ script**: `/app/harness/diff_plan.py`
- **DuckDB inventory path**: `/app/inventory/workstations.duckdb`
- **Golden plans directory**: `/app/golden`
- **Postmortem path**: `/app/postmortem/postmortem.md`

Any deviation from these strings triggers a failure. In particular, typos in
the action strings are the single most common cause of submission rejection;
the submitter is strongly encouraged to generate the action strings via a Rego
helper rule rather than by hand-inlining them at every emission site.



## Postmortem end marker

End of postmortem. The next revision cadence is documented in Appendix X.
