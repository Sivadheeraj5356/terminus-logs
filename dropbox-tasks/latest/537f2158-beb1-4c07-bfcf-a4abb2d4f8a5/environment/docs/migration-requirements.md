# FinchRender Systemd Migration — Output Schema Reference

This document specifies the required output formats for the TypeScript migration tooling.
It describes WHAT the output must contain, not HOW to produce it.

## contracts.json

Written to `/app/output/contracts.json` by the `extract` CLI command.

```json
{
  "user": "<string>",
  "group": "<string>",
  "sockets": ["<path>"],
  "capabilities": ["<CAP_NAME>"],
  "cache_dirs": ["<path>"],
  "checkpoint_dir": "<path>",
  "env_vars": { "<KEY>": "<value>" },
  "policy_exceptions": [
    { "path": "<path>", "access": "read|write|rw", "rationale": "<string>" }
  ],
  "fd_count_observed": <number>,
  "syscall_set": ["<syscall_name>"]
}
```

### Field Requirements

**user** — The username the coordinator process runs as after privilege drop. Derived from
the strace `setuid` syscall argument, resolved to a name via `/etc/passwd`. Must match the
`service.user` value in `coordinator.yaml`.

**group** — The group name after privilege drop. Derived from the strace `setgid` syscall
argument, resolved via `/etc/group`.

**sockets** — Array of UNIX socket paths. Derived from `bind()` syscalls with `AF_UNIX`
family in the strace log.

**capabilities** — Array of capability names (e.g., `"CAP_SYS_NICE"`). Must be derived from
the FINAL `capset` call's `effective` set in the strace log. Capabilities present in
pre-drop `capget` results must NOT be included unless confirmed in the final `capset`.

**cache_dirs** — Array of directory paths the coordinator opens and holds open. Derived from
strace `openat(..., O_RDONLY|O_DIRECTORY, ...)` calls that appear in the lsof steady-state
output with `DIR` type and a numbered fd (not `cwd`/`rtd`).

**checkpoint_dir** — The filesystem path where the coordinator writes job checkpoint files.
Derived from the `checkpoints.dir` key in `/app/legacy/coordinator.yaml`. This directory
was introduced in coordinator v2.0.0 and must be included in `ReadWritePaths=` in the
systemd service unit.

**env_vars** — Object of environment variable name-value pairs. Derived from the strace
`execve` call's third argument (envp array). Include only `FINCHRENDER_*` variables.

**policy_exceptions** — Array of OS-level access requirements documented in the operations
dossier (`/app/docs/ops-dossier.md`) that are not fully captured by the strace/lsof alone.
The tooling must search the dossier prose for mentions of paths that require special access.
Minimum: 3 entries (the three paths documented in the dossier).

**fd_count_observed** — Maximum open file descriptor count observed across all lsof captures.
Count only entries with numeric fd values (exclude `cwd`, `rtd`, `txt`, `mem`, `DEL`).

**syscall_set** — Sorted, deduplicated array of every syscall name observed across ALL strace
capture files under `/app/traces/` (i.e., `startup-cold.strace`, `startup-warm.strace`, and
`graceful-reload.strace`). This field powers the M4 syscall audit. The array must be sorted
alphabetically and contain no duplicates.

---

## Systemd Unit Files

Written to `/app/output/` by the `generate` CLI command.

### finchrender.service

A systemd service unit file. Required directives:

```ini
[Unit]
# Description, After=, and Requires= directives required
# After= must include: finchrender.socket network.target systemd-tmpfiles-setup.service
#                      local-fs.target udev-settle.service
# udev-settle.service is required so GPU device enumeration (/sys/class/drm) succeeds
# on hosts where the amdgpu/drm kernel module loads late (see ops dossier incident history).

[Service]
Type=exec
User=<from contracts.user>
Group=<from contracts.group>
EnvironmentFile=/etc/finchrender/finchrender.env
ExecStart=/usr/local/bin/finchrender-coordinator --config /etc/finchrender/coordinator.yaml --system /etc/finchrender/system.toml
Restart=on-failure
RestartSec=5s
# StartLimitBurst and StartLimitIntervalSec must reflect the restart policy documented
# in the operations dossier: maximum 5 restart attempts within a 10-minute window.
StartLimitBurst=5
StartLimitIntervalSec=10min

# Security (all required)
NoNewPrivileges=yes
PrivateTmp=yes
CapabilityBoundingSet=<from contracts.capabilities>
AmbientCapabilities=<from contracts.capabilities>
DeviceAllow=<from contracts.policy_exceptions where path starts with /dev/>

# ReadWritePaths must include the cache dirs, checkpoint dir, and log dir.
ReadWritePaths=/var/cache/finchrender /var/lib/finchrender /var/log/finchrender

# File descriptor limit: set to 64.
# Rationale: coordinator normal operation peaks at fd_count_observed (≤ 15).
# The limit of 64 = 2 × max_workers (16) × 2 provides headroom for worker
# connection bursts while still catching file descriptor leaks early
# (incident INC-2024-0033 showed the old ulimit of 256 was too permissive).
LimitNOFILE=64

# SystemCallFilter: use @system-service for common daemon syscalls.
# The coordinator additionally requires capget, capset, and prctl for its
# post-drop capability verification sequence; these are NOT covered by
# @system-service and must be added explicitly.
SystemCallFilter=@system-service
SystemCallFilter=capget capset prctl

[Install]
WantedBy=multi-user.target
```

### finchrender.socket

```ini
[Socket]
ListenStream=<from contracts.sockets[0]>

[Install]
WantedBy=sockets.target
```

### finchrender-tmpfiles.conf

```
# Runtime socket directory (created on every boot since /run is tmpfs)
d  /run/finchrender  0755  <user>  <group>  -

# Cache directories (D type: create and clear on every boot)
D  <cache_dir>  0750  <user>  <group>  -
```

One `d` entry for `/run/finchrender`, one `D` entry for each path in `contracts.cache_dirs`.

### finchrender.env

```bash
<KEY>=<value>
```

One line per entry in `contracts.env_vars`.

---

## validation-report.json

Written to `/app/output/validation-report.json` by the `validate` CLI command.

```json
{
  "passed": <boolean>,
  "policy_exceptions_covered": [
    { "path": "<path>", "directive": "<systemd-directive>" }
  ],
  "fd_count_valid": <boolean>,
  "fd_count_actual": <number>,
  "tmpfiles_complete": <boolean>,
  "limit_nofile_valid": <boolean>,
  "limit_nofile_found": <number>,
  "start_limit_policy_valid": <boolean>,
  "issues": ["<string>"]
}
```

### Validation Checks

**policy_exceptions_covered** — For each entry in `contracts.policy_exceptions`, verify
that `finchrender.service` contains a directive that provides the required access. Map:
- `/dev/*` path with `rw` access → `DeviceAllow=<path> rw` directive; the `directive`
  field in the covered entry must be the matching `DeviceAllow=` line from the service unit.
- `/proc/*` path → `ReadOnlyPaths=<path>` directive (or path not blocked by ProtectSystem)
- `/sys/*` path → accessible under `ProtectKernelTunables=yes` (read-only sysfs paths allowed)

**fd_count_valid** — Parse `/app/traces/under-load.lsof`. Count all entries with numeric
fd values (exclude `cwd`, `rtd`, `txt`, `mem`, `DEL`). Result must be ≤ 15.

**fd_count_actual** — The raw numeric count of persistent fds from `/app/traces/under-load.lsof`
(the same count used for `fd_count_valid`). Must be 15 for the provided capture.

**tmpfiles_complete** — Parse `finchrender-tmpfiles.conf`. Verify it contains an entry for
`/run/finchrender` (any type) and an entry for each path in `contracts.cache_dirs`.

**limit_nofile_valid** — Parse `finchrender.service`. Verify that `LimitNOFILE=` is present
and its value is greater than `contracts.fd_count_observed`. A limit of 64 satisfies this
for the observed count of 15.

**limit_nofile_found** — The numeric value of `LimitNOFILE=` as parsed from `finchrender.service`.
Must be 64 when the service unit is correctly generated. This field must be populated even
when `limit_nofile_valid` is false, so the caller can see what value was found.

**start_limit_policy_valid** — Parse `finchrender.service`. Verify that both
`StartLimitBurst=5` and `StartLimitIntervalSec=10min` are present, matching the restart
policy documented in the operations dossier.

**passed** — Set to `true` if all checks pass (policy_exceptions_covered is non-empty and
covers all policy_exceptions paths, fd_count_valid is true, tmpfiles_complete is true,
limit_nofile_valid is true, start_limit_policy_valid is true, and issues array is empty).
Otherwise `false`.

**issues** — Array of human-readable strings describing any failing checks. Empty if passed.

---

## syscall-audit.json

Written to `/app/output/syscall-audit.json` by the `audit` CLI command.

```json
{
  "syscalls_observed": ["<syscall_name>"],
  "extra_syscalls": ["<syscall_name>"],
  "sysctl_required": { "<key>": "<value>" }
}
```

### Field Requirements

**syscalls_observed** — Sorted, deduplicated array of all syscall names observed across all
`.strace` files in `/app/traces/`. Must match `contracts.syscall_set`.

**extra_syscalls** — Subset of `syscalls_observed` that are NOT covered by systemd's
`@system-service` syscall group. These are the syscalls that must be added as an explicit
second `SystemCallFilter=` line in the service unit. The required extra syscalls for the
FinchRender coordinator are: `capget`, `capset`, `prctl` (capability management and
securebits configuration). Do NOT include `setuid` or `setgid` — with systemd's `User=`
directive, the coordinator starts as the target user and those calls are no-ops.

**sysctl_required** — Kernel parameter values that must be enforced on the coordinator host.
The coordinator requires `kernel.shmmax >= 67108864` (64 MB) as documented in the post-
mortem for INC-2022-0034. Include exactly `{ "kernel.shmmax": "67108864" }`.

---

## 99-finchrender-shmmax.conf

Written to `/app/output/99-finchrender-shmmax.conf` by the `audit` CLI command.
This is a sysctl.d configuration file that enforces the shared-memory ceiling.

Format:
```
kernel.shmmax = 67108864
```

The value 67108864 (64 MB) is the minimum `kernel.shmmax` required by the coordinator
as documented in INC-2022-0034 and recorded in `/etc/sysctl.d/99-finchrender.conf` on
production hosts.

---

## finchrender-drop-in.conf

Written to `/app/output/finchrender-drop-in.conf` by the `audit` CLI command.
This is a systemd service override (drop-in) file that adds the `SystemCallFilter`
directives derived from the syscall audit.

Format:
```ini
[Service]
SystemCallFilter=@system-service
SystemCallFilter=<space-separated extra_syscalls>
LimitNOFILE=64
```

The drop-in format allows these hardening directives to be maintained separately from the
base service unit and applied via `systemctl edit finchrender.service`.
