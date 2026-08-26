# FinchRender Coordinator Operations Dossier

**Document ID:** FRCRD-OPS-001  
**Classification:** Internal — Infrastructure Team  
**Owner:** Platform Engineering  
**Last Reviewed:** 2024-10-15  
**Review Cycle:** Quarterly  

---

## Revision History

| Rev | Date | Author | Summary |
|-----|------|--------|---------|
| 1.0 | 2022-01-10 | JM | Initial document creation; baseline coordinator v1.0.0 |
| 1.1 | 2022-04-22 | AR | Added incident reports INC-2022-0012 through INC-2022-0034 |
| 1.2 | 2022-09-05 | PK | Updated privilege model section; documented privilege drop sequence |
| 1.3 | 2023-01-18 | JM | Expanded historical ops log through Q4 2022; added capacity planning |
| 2.0 | 2023-06-01 | AR | Major revision: runtime behaviour analysis from strace/lsof sessions |
| 2.1 | 2023-11-14 | PK | Security posture review; added Section 5 in full |
| 2.2 | 2024-03-20 | TL | OS integration requirements for systemd migration planning |
| 2.3 | 2024-10-15 | AR | Migration planning decisions; capability audit results |

---

## Section 1: Executive Summary

FinchRender is a distributed render-farm coordination platform used internally by the Visual
Effects pipeline. The coordinator process (`finchrender-coordinator`) is the central scheduler
and job dispatcher that receives render jobs from the submission frontend, dispatches tiles to
worker nodes, and tracks job completion. It has been running in production since January 2022
and currently handles approximately 8,000 render-hours per day across 14 production render
nodes.

The coordinator runs as a long-lived daemon process, starting as root to bind the privileged
coordination socket and then dropping privileges to the `finchrender` user (uid 2771) in the
`render` group (gid 2001). This privilege drop model has been in place since coordinator v1.1.0
(released 2022-02-15). Prior to that version, the coordinator ran as root throughout its
lifetime, which was identified as a critical security finding in the 2022 Q1 infrastructure
review.

The coordinator exposes a UNIX domain socket at `/run/finchrender/coordinator.sock` for
inter-process communication with worker nodes and the job submission gateway. All worker-to-
coordinator communication flows through this socket. There is no TCP listener; network-level
access is not required and has never been enabled.

Cache directories under `/var/cache/finchrender/` are maintained by the coordinator for
tile-level render outputs (`tiles/`), assembled frame buffers (`frames/`), and compiled shader
programs (`shaders/`). These directories are opened at startup and held open throughout the
coordinator's lifetime to avoid repeated permission checks and to enable atomic cache
management operations.

The current startup model relies on a launcher script (`/usr/local/bin/finchrender-launcher`)
that sources environment variables from `/etc/finchrender/environment` and then exec's the
coordinator binary with root privileges. The coordinator itself handles the privilege drop. This
model is being replaced with systemd-native service management as part of the platform hardening
initiative approved in Q3 2024.

This document captures the full operational history, runtime behaviour profile, security posture
analysis, and migration planning decisions needed to produce the target systemd unit files. It
consolidates knowledge that has historically been scattered across Slack threads, runbooks in
Notion, and tribal knowledge held by the platform team.

---

## Section 2: Architecture Overview

The FinchRender system consists of four primary components:

**Coordinator (`finchrender-coordinator`)**  
Central scheduler and dispatcher. Single instance per render cluster. Accepts job submissions
via the UNIX socket, maintains the in-memory job queue, and dispatches tiles to available
workers. Holds the canonical view of cluster state.

**Worker Nodes (`finchrender-worker`)**  
Distributed render executors. Each worker runs on a dedicated machine with GPU access. Workers
connect to the coordinator socket at startup and receive tile work items via the IPC protocol.
Workers report completion via the same channel. The coordinator maintains persistent connections
to all registered workers.

**Job Submission Gateway (`finchrender-gateway`)**  
HTTP frontend that translates artist-facing REST API calls into coordinator IPC messages. The
gateway authenticates users, validates scene packages, and enqueues job specifications. It
connects to the coordinator socket and holds a persistent connection.

**Cache Manager (`finchrender-cache`)**  
Background process that manages the LRU eviction policy for the tile and frame cache
directories. It monitors cache directory size via inotify and prunes entries when usage exceeds
configured thresholds. It communicates with the coordinator via a separate control socket
(`/run/finchrender/cache-manager.sock`) to coordinate eviction with active job tracking.

```
  [Artist Workstation]
         |
         v HTTP
  [Gateway Service]
         |
         v UNIX socket: /run/finchrender/coordinator.sock
  [Coordinator Process]  <----> [Cache Manager]
         |
         v UNIX sockets (per worker)
  [Worker-01] [Worker-02] ... [Worker-14]
         |
         v (GPU)
  [/dev/dri/renderD128 on each worker host]
```

The coordinator machine itself also has a GPU (`/dev/dri/renderD128`) used for thumbnail
generation and scene pre-processing. This GPU access is opened during startup as part of the
hardware enumeration phase. The coordinator enumerates available GPU devices by scanning
`/sys/class/drm/` and opening each device file to check capabilities.

The coordinator is designed to be single-threaded with an event loop (using `epoll`). All I/O
is non-blocking. Worker connections are maintained as persistent UNIX sockets in the event loop's
file descriptor set. The number of simultaneously open file descriptors scales with the number
of connected workers but is bounded by the `max_workers` configuration (default 16), socket
for the main listener, logging, configuration files, and GPU device handle.

### 2.1 Coordinator Startup Sequence

1. Read `/etc/finchrender/coordinator.yaml` and `/etc/finchrender/system.toml`
2. Parse command-line arguments and environment overrides
3. Validate shared-memory system parameters
4. Call `setgid(2001)` to drop to group `render`
5. Call `setuid(2771)` to drop to user `finchrender`
6. Call `capset` to establish the post-drop capability mask
7. Create and bind the UNIX socket
8. Open GPU device and enumerate DRM devices
9. Open cache directories
10. Enter the `epoll` event loop

### 2.2 Configuration Hierarchy

The coordinator uses a three-layer configuration hierarchy:

1. **Compiled defaults** — values baked into the binary, used when no config is present
2. **Config files** — `/etc/finchrender/coordinator.yaml` and `/etc/finchrender/system.toml`
3. **Environment overrides** — `FINCHRENDER_*` variables override config file values

Environment variables take precedence over config file values. This allows systemd unit files
to inject runtime tuning without modifying config files on disk.

Current environment variables used by the coordinator:

| Variable | Default | Description |
|----------|---------|-------------|
| `FINCHRENDER_TILE_WORKERS` | 4 | Number of concurrent tile-dispatch worker threads |
| `FINCHRENDER_FRAME_BUFFER_MB` | 256 | Size of the in-memory frame assembly buffer |
| `FINCHRENDER_SOCKET_TIMEOUT` | 60 | Worker connection idle timeout in seconds |
| `FINCHRENDER_LOG_LEVEL` | warn | Logging verbosity (debug, info, warn, error) |

In the current production configuration these are set to: `FINCHRENDER_TILE_WORKERS=8`,
`FINCHRENDER_FRAME_BUFFER_MB=512`, `FINCHRENDER_SOCKET_TIMEOUT=30`, and
`FINCHRENDER_LOG_LEVEL=info`. These values were tuned during the Q2 2023 capacity planning
review and have been stable since.

---

## Section 3: Historical Operations Log

### 3.1 Deployment History

**2022 Q1 — Initial Deployment (coordinator v1.0.0)**  
Initial production deployment to prod-render-01 through prod-render-04. System ran as root
throughout its lifetime. Four worker nodes, 200 render-hours/day peak. Deployment performed
manually by JM following the installation runbook. No systemd integration at this point;
coordinator was started via `/etc/rc.local` entry and a cron job for restart-on-failure
monitoring.

**2022 Q2 — Security Remediation and v1.1.0 Upgrade**  
Following the Q1 infrastructure security review, running as root was identified as
unacceptable. Coordinator v1.1.0 introduced the privilege-drop model: the process starts as
root, binds the socket (which has root-owned directory requirements), then drops to uid 2771
(`finchrender`) and gid 2001 (`render`). The `finchrender` user was created by AR using
`useradd -r -u 2771 -g render -d /var/lib/finchrender -s /usr/sbin/nologin finchrender`.
This upgrade required all four nodes to be restarted sequentially during a maintenance window.

**2022 Q3 — Scale-out to 8 Workers**  
Additional render capacity added: prod-render-05 through prod-render-08. Worker count grew from
4 to 8. Peak throughput increased to approximately 1,200 render-hours/day. The coordinator
handled the increased worker connections without issues, though the `max_workers` configuration
was raised from the default of 8 to 12 to provide headroom.

**2022 Q4 — Coordinator v1.3.0 Upgrade (GPU Thumbnail Support)**  
This release added GPU-accelerated thumbnail generation for the job review interface. The
coordinator process now opens `/dev/dri/renderD128` during startup for direct rendering
device access. This was the first time the coordinator required a device file handle. The
`render` group was given read-write access to the DRM device: `chown root:render /dev/dri/renderD128
&& chmod 660 /dev/dri/renderD128`. The `finchrender` user is a member of the `render` group
so it inherits this access after the privilege drop.

The coordinator also gained the ability to enumerate available GPU devices at startup by reading
the DRM device list from sysfs. The enumeration code scans `/sys/class/drm/` for available
render devices.

**2023 Q1 — Monitoring and Alerting Overhaul**  
Prometheus exporter added to the coordinator. New metrics: `frc_jobs_queued`,
`frc_jobs_dispatched_total`, `frc_workers_connected`, `frc_cache_hit_ratio`,
`frc_socket_accept_latency_ms`. Alerting rules added to PagerDuty for:
queue depth > 500 for > 5 minutes, worker count dropping below 6, and cache hit ratio
below 0.6 for > 10 minutes.

**2023 Q2 — Capacity Planning and Tuning**  
Following analysis of 6 months of metrics, the platform team adjusted the coordinator
tuning parameters. `FINCHRENDER_TILE_WORKERS` was raised from 4 to 8 (doubling tile-dispatch
parallelism). `FINCHRENDER_FRAME_BUFFER_MB` was raised from 256 to 512 to accommodate
4K frame assembly. `FINCHRENDER_SOCKET_TIMEOUT` was reduced from 60 to 30 to accelerate
detection of stale worker connections. `FINCHRENDER_LOG_LEVEL` was set to `info` (from `warn`)
to enable operational visibility without debug noise.

**2023 Q3 — Scale-out to 12 Workers**  
prod-render-09 through prod-render-12 added. Scale-out was uneventful. The coordinator's
per-worker socket management handled the additional connections without changes.

**2023 Q4 — Coordinator v2.0.0 Upgrade (Checkpoint Support)**  
Major version upgrade introducing checkpoint support for in-flight jobs during coordinator
restarts. Checkpoint state is written to `/var/lib/finchrender/checkpoints/`. The coordinator
now requires write access to this directory. Added to the deployment checklist.

**2024 Q1 — Security Audit and Hardening Review**  
Annual security audit identified several improvement opportunities:
1. The coordinator still starts as root; even though it drops privileges quickly, the window
   is undesirable.
2. Capability bounding set has never been formally documented.
3. No systemd integration means process supervision relies on custom scripts that have had
   reliability issues (see INC-2024-0021).
The audit recommended migrating to systemd with socket activation and explicit capability
bounding.

**2024 Q2 — Scale-out to 14 Workers**  
prod-render-13 and prod-render-14 added.

**2024 Q3 — Systemd Migration Planning Approved**  
Architecture review board approved the systemd migration initiative. Target completion Q4 2024.
This dossier was updated with Section 6 (OS Integration Requirements) and Section 7 (Migration
Planning Decisions) to support the migration effort.

---

### 3.2 Incident Reports

**INC-2022-0012 — Coordinator Failed to Restart After Host Reboot**  
*Date:* 2022-03-14 03:22 UTC  
*Severity:* P2 (Production Impact)  
*Reporter:* Automated monitoring (PagerDuty alert: worker_count < 6)  
*Author:* JM  

*Summary:* After a scheduled kernel upgrade reboot of the coordinator host
(prod-render-01), the coordinator process failed to start. The `rc.local`-based startup
sequence had a race condition with the `/run` tmpfs mount: the startup script ran before
`/run/finchrender/` was created, so the socket bind failed with ENOENT.

*Resolution:* Added `mkdir -p /run/finchrender` to the coordinator startup script before the
exec call. Also added a 5-second sleep after the `rc.local` entry to allow tmpfs mounts to
settle. This is a known limitation of the `rc.local` approach and further reinforces the
case for systemd-native management with `tmpfiles.d` for directory creation.

*Action Items:*
- Short-term: Fixed startup script (deployed 2022-03-14 during the incident).
- Long-term: Migrate to systemd with proper `tmpfiles.d` integration (deferred; prioritised
  for 2024 Q4 hardening initiative).

---

**INC-2022-0019 — Cache Directory Permission Error After Manual Cleanup**  
*Date:* 2022-05-03 14:07 UTC  
*Severity:* P3 (Degraded Performance)  
*Reporter:* AR  

*Summary:* A manual cache cleanup operation by AR incorrectly changed the ownership of
`/var/cache/finchrender/tiles` to `root:root`. The coordinator was running at the time and
had the directory open (fd 6), so it did not notice immediately. After a coordinator restart
triggered by a config change deployment, the coordinator failed to reopen the tiles cache
directory because `finchrender` no longer had read access.

*Resolution:* Restored correct ownership: `chown finchrender:render /var/cache/finchrender/tiles`.
Coordinator restarted and reconnected workers within 90 seconds.

*Root Cause:* Manual `rm -rf` of cache contents was executed as root without first verifying
ownership of the parent directory. The cleanup script used `find /var/cache/finchrender -mtime +7
-delete` without the necessary chown restoration step.

*Action Items:*
- Added ownership verification to the cache prune runbook.
- Created automated test that verifies cache directory ownership after any maintenance operation.

---

**INC-2022-0034 — Coordinator OOM Kill During Large Frame Assembly**  
*Date:* 2022-08-22 09:45 UTC  
*Severity:* P2 (Production Impact)  
*Reporter:* PK  
*Author:* PK  

*Summary:* The coordinator was OOM-killed by the kernel during assembly of a 8K HDR frame
with 256 tiles. Peak memory usage reached 3.1 GB, exceeding the 3 GB RSS limit observed
during tuning. Investigation revealed two contributing factors.

First, the frame buffer size was configured at 256 MB (`FINCHRENDER_FRAME_BUFFER_MB=256`) but
the actual allocation for 8K HDR exceeded this when the inter-tile blending pass ran.

Second, and more subtly, the coordinator was allocating shared memory segments for the GPU
thumbnail pipeline. On this host, the kernel's shared memory ceiling was set lower than
the coordinator's default request size. The coordinator calls `shmget(IPC_PRIVATE, requested_size,
IPC_CREAT|0600)` and was falling back to a smaller segment size when `shmget` failed, but
the fallback path had a memory leak (coordinator bug, fixed in v1.3.2).

*The coordinator reads `/proc/sys/kernel/shmmax` at startup to verify the system shared
memory ceiling before attempting any `shmget` calls.* This check was introduced in v1.2.0
as a pre-flight validation step. On this host the shmmax was 33554432 (32 MB), which
the coordinator logged as a warning but did not treat as fatal. The bug in the fallback
path meant that when the coordinator fell back from the requested 64 MB segment to a 16 MB
segment, the original 64 MB mapping was not released.

*Resolution:*
1. Upgraded coordinator to v1.3.2 (shmget fallback memory leak fix).
2. Set `kernel.shmmax = 67108864` (64 MB) in `/etc/sysctl.d/99-finchrender.conf` on all
   coordinator hosts.
3. Raised `FINCHRENDER_FRAME_BUFFER_MB` to 512 in anticipation of the Q2 2023 tuning review.

*Action Items:*
- All coordinator hosts must have `kernel.shmmax >= 67108864`.
- Added shmmax check to the deployment pre-flight checklist.
- Coordinator startup now treats shmmax < 32 MB as a fatal error (v1.4.0).

---

**INC-2022-0041 — Worker Registration Storm After Network Partition**  
*Date:* 2022-11-07 16:33 UTC  
*Severity:* P2 (Production Impact)  
*Reporter:* Automated monitoring  
*Author:* JM  

*Summary:* A 45-second network partition between the coordinator host and all 8 worker nodes
caused all workers to disconnect simultaneously. When the partition healed, all 8 workers
attempted to reconnect to the coordinator socket simultaneously. The coordinator's accept
loop processed these in rapid succession, but the initial burst of registration IPC messages
overwhelmed the single-threaded event loop for approximately 90 seconds.

During this window, the job submission gateway (which also uses the coordinator socket) failed
to get a response to its keepalive message and declared the coordinator unhealthy, removing it
from the load balancer's backend pool. This caused job submission errors for end users.

*Resolution:* Added exponential backoff to the worker reconnect logic (coordinator v1.2.1).
Workers now wait a random 0-30 second delay before attempting reconnection, with backoff up
to 5 minutes on repeated failures. The gateway's keepalive timeout was extended from 5 to 30
seconds to tolerate brief processing spikes.

---

**INC-2023-0008 — Socket File Left After Unclean Shutdown**  
*Date:* 2023-02-11 04:18 UTC  
*Severity:* P3 (Degraded Performance, delayed recovery)  
*Reporter:* On-call engineer (AR)  
*Author:* AR  

*Summary:* The coordinator host was hard-rebooted due to a kernel panic. After the reboot, the
coordinator failed to start because `/run/finchrender/coordinator.sock` already existed as a
stale socket file left over from the previous (unclean) shutdown. The `bind(2)` call returned
EADDRINUSE.

Note: `/run` is a tmpfs mount that is recreated on boot. On this host, the `/run/finchrender`
directory had been created with sticky bit set, and the socket file was created before the
crash as a bind-mounted overlay (an investigation artefact from a previous unrelated debugging
session). The overlay was not cleaned up correctly during the reboot.

*Resolution:* The coordinator startup script was updated to always unlink the socket file
before binding (using `SO_REUSEADDR` is not applicable to UNIX domain sockets in the same
way as TCP sockets). The correct idiom is: `unlink(path)` before `bind(2)`. This was already
the behavior in coordinator v1.2.0+ for normal shutdowns; the change was to also handle the
startup case where the file exists but the process is not running.

*Long-term:* With systemd socket activation, the socket file lifecycle is managed by systemd
itself, and this class of startup race is eliminated.

---

**INC-2023-0021 — Monitoring Script Restart Loop Caused CPU Spike**  
*Date:* 2023-05-29 22:14 UTC  
*Severity:* P3 (Performance Degraded)  
*Reporter:* PK  

*Summary:* The custom coordinator restart monitoring script (`/usr/local/bin/check-coordinator.sh`)
entered a tight restart loop after the coordinator exited with a non-zero code (exit code 1)
due to a configuration validation failure introduced by a bad config push. The script was
configured to restart the coordinator immediately on failure, without any backoff or failure
count limit. The tight restart loop consumed significant CPU and I/O, degrading the coordinator
host.

*Root Cause:* The config push set `socket_timeout: -1` in coordinator.yaml, which the
coordinator treats as a validation error (negative timeouts are not allowed). The coordinator
exited with code 1 on every attempt, and the monitoring script restarted it immediately.

*Resolution:*
1. Fixed the config validation error (rolled back the bad push).
2. Added a 30-second backoff and a maximum of 5 restart attempts per 10-minute window to the
   monitoring script.
3. Opened the long-term ticket to migrate to systemd (which handles restart policy natively
   and cleanly).

---

**INC-2023-0037 — Tile Cache Corruption During Coordinator Failover**  
*Date:* 2023-09-12 10:05 UTC  
*Severity:* P2 (Production Impact)  
*Reporter:* Automated monitoring (cache_hit_ratio alert)  
*Author:* TL  

*Summary:* During a coordinator restart (triggered by an operator for a config change), two
render jobs were in-flight in the tile assembly phase. The coordinator shutdown flushed the
frame buffer but did not atomically commit the partial tile writes. On startup, the cache
manager read the partial tile files as valid (they had valid file headers but were truncated)
and served them to workers on subsequent requests. The resulting frames had corrupted regions.

The corrupted renders were caught during QA review (approximately 45 minutes after the
incident) rather than being automatically detected.

*Resolution:*
1. Added a tile integrity check (SHA-256 hash verification) to the cache manager's read path.
2. Added a coordinator shutdown hook that marks in-progress tile writes with a `.partial`
   extension until they are completed.
3. Updated the cache manager to skip and delete any `.partial` files found during startup scan.

---

**INC-2024-0007 — GPU Enumeration Failure on Kernel Upgrade**  
*Date:* 2024-01-08 08:22 UTC  
*Severity:* P2 (Production Impact)  
*Reporter:* JM  
*Author:* JM  

*Summary:* After a kernel upgrade from 5.15.0 to 6.1.0 on prod-render-01, the coordinator
failed to start. The startup logs showed: `FATAL: GPU enumeration failed: stat(/sys/class/drm)
returned ENOENT`. Investigation revealed that the sysfs DRM subsystem path had changed in
kernel 6.1 on this specific hardware configuration.

*Root Cause:* The kernel 6.1 driver module was not loaded at the time the coordinator attempted
the sysfs enumeration. The `amdgpu` module was loaded as a kernel module that requires
firmware files to be available before initialization. The coordinator started before
`systemd-udevd` had finished loading the GPU firmware, so `/sys/class/drm` existed as a
directory but contained no device entries, and the coordinator treated this as a fatal error.

*Resolution:*
1. Added a retry loop (3 attempts, 2-second delay) to the GPU enumeration code.
2. Added `After=sys-devices-virtual.mount` ordering hint to the startup script.
3. With systemd integration (planned), proper `After=udev-settle.service` ordering will
   handle this correctly.

---

**INC-2024-0021 — Coordinator Restart Script Hung on Lock File**  
*Date:* 2024-04-22 03:11 UTC  
*Severity:* P3 (Recovery Delayed)  
*Reporter:* Automated monitoring  
*Author:* AR  

*Summary:* The coordinator process died with SIGSEGV (a bug that was subsequently fixed in
v2.0.4). The monitoring script attempted to restart it, but the coordinator's PID file at
`/run/finchrender/coordinator.pid` was not removed by the abnormal exit. The restart script
checks for the PID file and refuses to start a second coordinator instance if the PID file
exists. The script incorrectly interpreted a stale PID file as an indication that the process
was still running.

The monitoring alert fired, on-call was paged, and the engineer manually removed the PID file
before restarting. Downtime: 12 minutes.

*Resolution:*
1. Restart script updated to verify that the process with the PID in the PID file is actually
   alive before refusing to start.
2. Coordinator v2.0.4 deployed (SIGSEGV fix).
3. This incident is the direct trigger for accelerating the systemd migration: systemd
   manages PID lifecycle natively and does not have this class of stale-PID-file problem.

---

**INC-2024-0033 — Worker Connection Leak Under High Job Rate**  
*Date:* 2024-06-18 15:42 UTC  
*Severity:* P2 (Production Impact)  
*Reporter:* PK  
*Author:* PK  

*Summary:* Under sustained high job submission rate (>200 jobs/hour), the coordinator
accumulated stale worker connections that were not being properly cleaned up. The file
descriptor count (observed via `lsof -p $(pgrep finchrender-coordinator)`) climbed steadily
from the expected ~20 to over 200 over a 4-hour period. The coordinator eventually exhausted
its file descriptor limit (ulimit -n was 256) and began failing to accept new worker
connections.

*Root Cause:* In coordinator v2.0.2, a refactoring of the epoll notification path introduced
a bug where worker disconnection events were correctly detected but the corresponding socket
file descriptors were not closed (the `close(fd)` call was moved to a code path that required
an additional `EPOLLRDHUP` event that was not being generated on this kernel version).

*Resolution:*
1. Hot patch applied to production (coordinator v2.0.3).
2. Post-fix, the coordinator's steady-state FD count returned to the expected range. Under
   normal operation with 14 connected workers, the coordinator maintains no more than 15
   open file descriptors per process (this count excludes mem and txt mappings reported by
   lsof; the actual kernel fd table size is 13 to 15 descriptors for the combination of:
   stdin/stdout/stderr, config file handles, the listener socket, cache directory handles,
   shmmax proc entry, GPU device handle, and the epoll file descriptor).
3. Added FD count monitoring to the Prometheus exporter.

---

**INC-2024-0041 — Shmmax Threshold Warning Suppressed by Log Level Change**  
*Date:* 2024-07-30 11:00 UTC  
*Severity:* P4 (Warning, No Production Impact)  
*Reporter:* TL  
*Author:* TL  

*Summary:* A temporary change to `FINCHRENDER_LOG_LEVEL=warn` (from `info`) during a
diagnostic investigation caused the shmmax pre-flight check warning to be suppressed. The
check itself still ran, but the coordinator's logging was at `warn` level and the shmmax
check emits an `INFO`-level message. After the diagnostic session, the log level was left at
`warn` for approximately 3 days before being noticed. During this period, a second host
(prod-render-03) had its shmmax reduced as a side effect of a kernel parameter tuning script,
but the coordinator on that host did not produce a visible warning.

*Resolution:*
1. Restored `FINCHRENDER_LOG_LEVEL=info` across all coordinator hosts.
2. Added an explicit `ERROR`-level log entry for the shmmax check failure case (shmmax
   below the required minimum), separate from the `INFO`-level summary.
3. Log level changes to production coordinators now require a change review ticket.

---

**INC-2024-0055 — Coordinator Failed Start Due to Missing Cache Directory**  
*Date:* 2024-09-04 02:55 UTC  
*Severity:* P2 (Production Impact)  
*Reporter:* Automated monitoring (worker_count alert)  
*Author:* AR  

*Summary:* The coordinator failed to start on prod-render-07 after a storage volume
re-provisioning. The `/var/cache/finchrender/` directory hierarchy did not exist on the new
volume. The coordinator attempts to open each cache directory (`tiles`, `frames`, `shaders`)
during startup and treats a failure as fatal.

*Root Cause:* The reprovisioning procedure did not include a step to recreate the cache
directory hierarchy.

*Resolution:*
1. Created the directories and set correct ownership: `install -d -m 0750 -o finchrender
   -g render /var/cache/finchrender/{tiles,frames,shaders}`.
2. Updated the host provisioning playbook to include cache directory creation.
3. With systemd's `tmpfiles.d` integration (planned for Q4 2024), the `D` directive will
   automatically create and set ownership on these directories on every boot.

---

### 3.3 Configuration Change Log

| Date | Change | Author | Ticket |
|------|--------|--------|--------|
| 2022-01-10 | Initial deployment; all defaults | JM | INFRA-0001 |
| 2022-02-15 | Upgrade to v1.1.0; privilege drop introduced | AR | INFRA-0018 |
| 2022-03-14 | Startup script fix for /run/finchrender race (INC-2022-0012) | JM | INC-2022-0012 |
| 2022-04-01 | Raised max_workers from 8 to 12 for Q2 scale-out | AR | INFRA-0031 |
| 2022-05-04 | Cache directory ownership fix (INC-2022-0019) | AR | INC-2022-0019 |
| 2022-08-23 | shmmax raised to 67108864 on all hosts (INC-2022-0034) | PK | INC-2022-0034 |
| 2022-08-23 | FINCHRENDER_FRAME_BUFFER_MB raised from 256 to 512 | PK | INC-2022-0034 |
| 2022-11-08 | Upgrade to v1.2.1; worker reconnect backoff (INC-2022-0041) | JM | INC-2022-0041 |
| 2022-12-01 | Upgrade to v1.3.0; GPU support added | TL | INFRA-0089 |
| 2022-12-01 | render group given rw access to /dev/dri/renderD128 | TL | INFRA-0089 |
| 2023-02-12 | Socket unlink-before-bind fix deployed (INC-2023-0008) | AR | INC-2023-0008 |
| 2023-04-15 | Prometheus exporter integration deployed | PK | INFRA-0112 |
| 2023-05-30 | Monitoring script backoff added (INC-2023-0021) | AR | INC-2023-0021 |
| 2023-06-01 | FINCHRENDER_TILE_WORKERS raised from 4 to 8 (capacity review) | AR | INFRA-0134 |
| 2023-06-01 | FINCHRENDER_SOCKET_TIMEOUT reduced from 60 to 30 (capacity review) | AR | INFRA-0134 |
| 2023-06-01 | FINCHRENDER_LOG_LEVEL changed from warn to info (capacity review) | AR | INFRA-0134 |
| 2023-09-13 | Cache integrity checks deployed (INC-2023-0037) | TL | INC-2023-0037 |
| 2023-12-01 | Upgrade to v2.0.0; checkpoint support | JM | INFRA-0201 |
| 2024-01-09 | GPU enumeration retry loop deployed (INC-2024-0007) | JM | INC-2024-0007 |
| 2024-04-23 | Upgrade to v2.0.4; SIGSEGV fix (INC-2024-0021) | AR | INC-2024-0021 |
| 2024-06-19 | Upgrade to v2.0.3 [sic; note: 2.0.4 deployed after]; FD leak fix | PK | INC-2024-0033 |
| 2024-07-31 | FINCHRENDER_LOG_LEVEL restored to info (INC-2024-0041) | TL | INC-2024-0041 |
| 2024-08-12 | Capability audit completed; CAP_CHOWN proposal REJECTED (see §7.2) | AR | INFRA-0287 |
| 2024-09-05 | Host provisioning playbook updated with cache dir creation step | AR | INC-2024-0055 |

---

## Section 4: Runtime Behaviour Analysis

This section documents the findings from the strace and lsof instrumentation sessions conducted
during Q3 2024 as part of the systemd migration preparation. All sessions were run on
prod-render-07 using coordinator v2.0.4.

### 4.1 Process Lifecycle

The coordinator binary (`/usr/local/bin/finchrender-coordinator`) is executed via `execve` by
the launcher script. The binary is statically linked against several shared libraries:
`libpthread.so.0`, `libc.so.6`, and `libstdc++.so.6`. These libraries are mapped into the
process address space during dynamic linking (before the coordinator's `main()` is reached).

The process startup sequence (instrumented with `strace -e trace=all`) proceeds as follows:

1. **Dynamic linking phase** (~80 syscalls): `mmap`, `mprotect`, `openat` (for `.so` files),
   `close`, `read`. These are standard dynamic linker operations and are not coordinator-specific.

2. **Configuration read phase**: `openat` for `/etc/finchrender/coordinator.yaml`, `read`,
   `close`; then `openat` for `/etc/finchrender/system.toml`, `read`, `close`.

3. **User/group lookup phase**: `openat` for `/etc/passwd`, `read`, `close`; `openat` for
   `/etc/group`, `read`, `close`. Used to resolve the `finchrender` username and `render`
   group name to numeric IDs.

4. **Capability query phase**: Two `capget` calls. The first retrieves the current capability
   header version. The second retrieves the full current capability bitmask (which at this
   point still includes the inherited root capabilities including `CAP_CHOWN`, `CAP_DAC_OVERRIDE`,
   `CAP_SETGID`, `CAP_SETUID`, `CAP_SYS_NICE`, and `CAP_NET_BIND_SERVICE`). These `capget`
   calls are informational; the pre-drop values should not be confused with the post-drop set.

5. **Privilege drop phase**: `setgid(2001)` drops to group `render`, then `setuid(2771)` drops
   to user `finchrender`. After the uid/gid drop, a final `capset` call establishes the
   post-drop capability mask.

6. **Secure bits phase**: `prctl(PR_SET_SECUREBITS, ...)` locks the `NOROOT` secure bit,
   preventing privilege re-escalation. Two `prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, ...)`
   calls raise `CAP_SYS_NICE` and `CAP_NET_BIND_SERVICE` into the ambient capability set.

7. **Shared memory validation**: Opens `/proc/sys/kernel/shmmax` for reading to check the
   system shared memory limit.

8. **Network/IPC phase**: `socket(AF_UNIX, SOCK_STREAM|SOCK_CLOEXEC, 0)` creates the
   coordinator socket (fd 5). `bind(5, {AF_UNIX, "/run/finchrender/coordinator.sock"})` binds
   it. `listen(5, 128)` starts accepting connections.

9. **Hardware phase**: `openat` for `/dev/dri/renderD128` (GPU device access) and
   `openat` for `/sys/class/drm` (GPU enumeration). Both are opened and quickly closed during
   startup enumeration; the GPU device may be re-opened later for render operations.

10. **Cache open phase**: `openat` for `/var/cache/finchrender/tiles` (fd 6),
    `/var/cache/finchrender/frames` (fd 7), `/var/cache/finchrender/shaders` (fd 8). These
    directory file descriptors are held open for the lifetime of the process.

11. **Event loop phase**: `epoll_create1`, `epoll_ctl` (add the coordinator socket),
    signal handler registration (`rt_sigaction` for SIGTERM and SIGHUP), then `epoll_wait`.

### 4.2 Privilege Model

The privilege drop sequence is the most security-sensitive part of the coordinator startup.
The strace session confirms the following sequence:

```
setgid(2001)  = 0     # drop to group "render"
setuid(2771)  = 0     # drop to user "finchrender"
capset({version=_LINUX_CAPABILITY_VERSION_3, pid=0},
       {effective=CAP_SYS_NICE|CAP_NET_BIND_SERVICE,
        permitted=CAP_SYS_NICE|CAP_NET_BIND_SERVICE,
        inheritable=0x0}) = 0
```

The `capset` call is critical. It establishes the post-drop capability mask explicitly. The
call sets both the `effective` and `permitted` sets to exactly `CAP_SYS_NICE` and
`CAP_NET_BIND_SERVICE`. The `inheritable` set is cleared to zero. No other capabilities are
present in the post-drop mask.

**Why `CAP_SYS_NICE`**: The coordinator uses `setpriority(2)` (via `nice(2)`) to lower the
priority of background tile-dispatch threads relative to the main coordinator event loop. This
allows the event loop to remain responsive to new connections even under heavy load. The
`CAP_SYS_NICE` capability is required to call `setpriority` with a negative `which` argument
(to increase, rather than decrease, the effective priority of the event loop thread).

**Why `CAP_NET_BIND_SERVICE`**: The coordinator socket is in `/run/`, which is a standard
filesystem path. However, the coordinator's IPC protocol also supports a mode where it binds
to a port in the privileged range (< 1024) for legacy compatibility with older worker node
configurations. `CAP_NET_BIND_SERVICE` ensures the coordinator can bind to such ports if the
configuration requests it. (Note: in the current production configuration, only the UNIX
socket is used, but the capability is retained to avoid breaking the fallback code path.)

The `capget` calls that precede the `capset` show the full root capability set — this is the
coordinator querying its current capabilities before dropping them. The pre-drop capabilities
(`CAP_CHOWN`, `CAP_DAC_OVERRIDE`, etc.) are NOT retained after the `capset` call.

### 4.3 IPC and Socket Usage

The coordinator creates one UNIX domain socket of type `SOCK_STREAM`:

```
socket(AF_UNIX, SOCK_STREAM|SOCK_CLOEXEC, 0) = 5
bind(5, {sa_family=AF_UNIX, sun_path="/run/finchrender/coordinator.sock"}, 48) = 0
listen(5, 128) = 0
```

The socket is at `/run/finchrender/coordinator.sock`. The directory `/run/finchrender/` must
exist before the coordinator starts; this is currently handled by the startup script and will
be handled by `tmpfiles.d` in the systemd migration.

The socket listen backlog of 128 was tuned in response to the Q3 2022 worker registration
storm (INC-2022-0041). With a backlog of 128, simultaneous reconnection storms from up to
128 workers can be buffered in the kernel's accept queue.

In the steady-state lsof output, this socket appears as fd 5 with type `unix` and the path
`/run/finchrender/coordinator.sock type=STREAM`. Under load, additional fds appear for
accepted worker connections (type `unix`, type=STREAM, no path shown — these are the connected
endpoints, not the listening socket).

### 4.4 File Descriptor Profile

The steady-state lsof output (captured under normal operation with 14 workers registered)
shows the following open file descriptors for the coordinator process:

| fd | Type | Path/Description |
|----|------|-----------------|
| 0 | REG | /dev/null (stdin) |
| 1 | REG | /var/log/finchrender/coordinator.log (stdout) |
| 2 | REG | /var/log/finchrender/coordinator.log (stderr) |
| 3 | REG | /etc/finchrender/coordinator.yaml |
| 4 | REG | /etc/finchrender/system.toml |
| 5 | unix | /run/finchrender/coordinator.sock (listening) |
| 6 | DIR | /var/cache/finchrender/tiles |
| 7 | DIR | /var/cache/finchrender/frames |
| 8 | DIR | /var/cache/finchrender/shaders |
| 9 | REG | /proc/sys/kernel/shmmax |
| 10 | CHR | /dev/dri/renderD128 |
| 11 | DIR | /sys/class/drm |
| 12 | a_inode | [eventpoll] |

This totals 13 file descriptors in the steady state (lsof entries with fd types `cwd`, `rtd`,
`txt`, and `mem` are excluded — these represent the working directory, root directory,
executable, and memory-mapped libraries respectively, and are not counted against the process's
open file descriptor count).

Under load (with active worker connections), the fd count rises proportionally to the number
of connected workers. Each worker connection adds one fd. The lsof capture from the under-load
session shows 2 additional worker connection fds (fds 13 and 14), bringing the total to 15.

**The coordinator process maintains no more than 15 open file descriptors during normal
operation**, even under maximum configured worker load. This bound was established during the
FD leak investigation (INC-2024-0033) and verified across multiple lsof sessions. The
`max_workers` configuration is set to 16, but in practice the coordinator reaches a maximum of
14 connected workers plus the 13 baseline fds = no more than 27 total; however, worker
connections at idle timeout (30 seconds, configured via `FINCHRENDER_SOCKET_TIMEOUT`) rather
than being held indefinitely. During the under-load snapshot, only 2 active connections were
observed, giving a total of 15 fds.

For the purposes of the systemd migration, the FD bound of 15 should be treated as the
expected maximum for steady-state operation with minimal concurrent worker load, and the
monitoring alert threshold should be set above this value to account for brief spikes during
worker reconnection storms.

### 4.5 Environment Variable Inventory

The coordinator's environment at startup is provided by the launcher script. The following
variables are consumed by the coordinator:

| Variable | Production Value | Source |
|----------|-----------------|--------|
| `FINCHRENDER_TILE_WORKERS` | `8` | /etc/finchrender/environment |
| `FINCHRENDER_FRAME_BUFFER_MB` | `512` | /etc/finchrender/environment |
| `FINCHRENDER_SOCKET_TIMEOUT` | `30` | /etc/finchrender/environment |
| `FINCHRENDER_LOG_LEVEL` | `info` | /etc/finchrender/environment |
| `PATH` | /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin | system |
| `HOME` | /var/lib/finchrender | launcher |
| `USER` | root | inherited (pre-drop) |

The `FINCHRENDER_*` variables are sourced from `/etc/finchrender/environment` by the launcher
script and passed to the coordinator via `execve`. They appear in the `execve` syscall's envp
argument in the strace output.

The variables are consumed at startup and not re-read during the process lifetime (with the
exception of `FINCHRENDER_LOG_LEVEL`, which can be changed at runtime via SIGHUP if the
coordinator is built with runtime log level support, which is the case in v2.0.0+).

---

## Section 5: Security Posture

### 5.1 Current Security Model

The coordinator's current security model is based on the privilege-drop approach established
in v1.1.0 (2022). The key elements are:

**Identity**: The coordinator runs as `finchrender` (uid 2771) in the `render` group (gid 2001)
after startup. The effective uid/gid after privilege drop is 2771/2001. All filesystem access
is governed by these IDs. The `/var/lib/finchrender/` home directory is owned by this user.
The `/run/finchrender/` runtime directory is created with ownership `finchrender:render 0755`.

**Capability set**: After privilege drop, the coordinator retains exactly two capabilities:
`CAP_SYS_NICE` and `CAP_NET_BIND_SERVICE`. The permitted, effective, and ambient capability
sets are all set to exactly these two capabilities. The inheritable set is zero.

**No new privileges**: The coordinator binary does not have the `setuid` bit set and does not
use any `PR_SET_NO_NEW_PRIVS`-style restrictions explicitly in v2.0.x. These restrictions will
be applied by the systemd unit file in the migration.

**Network exposure**: The coordinator has no TCP listeners. The only network-visible interface
is the UNIX socket at `/run/finchrender/coordinator.sock`, which is accessible only to
processes running as `finchrender` user or `render` group (socket permissions: 0660). There
is no external network attack surface.

**Filesystem access**: The coordinator accesses a well-defined set of paths:
- Configuration files in `/etc/finchrender/`
- Runtime socket in `/run/finchrender/`
- Cache directories in `/var/cache/finchrender/`
- Log files in `/var/log/finchrender/`
- State/checkpoint files in `/var/lib/finchrender/`
- System information files: `/proc/sys/kernel/shmmax`, `/etc/passwd`, `/etc/group`

### 5.2 Target Hardening Goals

The systemd migration will apply the following additional restrictions to the coordinator unit:

**NoNewPrivileges=yes**: Prevents any escalation via setuid binaries. Since the coordinator
only exec's known subprocesses (thumbnail encoder), this is safe to apply.

**ProtectSystem=strict**: Mounts `/usr`, `/boot`, `/efi` read-only. Since the coordinator
has no reason to write to these paths, this is safe.

**ProtectHome=yes**: Makes `/home` and `/root` inaccessible. The coordinator does not access
user home directories.

**PrivateTmp=yes**: Gives the coordinator its own private `/tmp` and `/var/tmp` namespace.

**RestrictAddressFamilies=AF_UNIX**: Since the coordinator only uses UNIX domain sockets,
all other address families can be blocked.

**RestrictNamespaces=yes**: The coordinator does not use Linux namespaces internally.

**SystemCallFilter**: Restrict allowed syscalls to the set observed in the strace session.
At minimum: `@system-service` set minus the rarely-used dangerous syscalls.

### 5.3 Device Access Requirements

The coordinator requires direct access to the GPU render device for thumbnail generation and
scene pre-processing operations. This access is required throughout the coordinator's lifetime,
not just at startup.

The GPU device is `/dev/dri/renderD128`. This is the primary render device on the coordinator
host. The `finchrender` user inherits access to this device through membership in the `render`
group, which has `rw` permission on the device (permissions: `crw-rw---- root:render 226,128`).

In the systemd unit file, the GPU device must be listed as a **required device access
allowance** in the `DeviceAllow` directive. Without this directive, the `PrivateDevices=yes`
or `DevicePolicy=closed` hardening would block access to `/dev/dri/renderD128`, preventing
the coordinator from performing thumbnail generation.

The `DeviceAllow` entry should read: `DeviceAllow=/dev/dri/renderD128 rw`

This allows the character device file at the specific path with read-write access. The
`render` group ownership of the device node is sufficient for filesystem-level access, but
the systemd `DevicePolicy` mechanism operates at the cgroup level and requires explicit
allowlisting of devices, independently of filesystem permissions.

### 5.4 Network Exposure

The coordinator has zero TCP/IP network exposure. All inter-process communication is via
the UNIX domain socket. The `RestrictAddressFamilies` directive in the systemd unit should
be set to `AF_UNIX` exclusively.

If in the future the coordinator's legacy TCP fallback mode is enabled (which it currently is
not), `AF_INET` and `AF_INET6` would need to be added to `RestrictAddressFamilies`. This is
explicitly not the case in the current production configuration.

External network connections to the coordinator are not possible and should remain impossible.
Monitoring access is via the Prometheus exporter, which is a separate process that reads from
the coordinator's shared memory segment — it does not expose the coordinator socket externally.

### 5.5 Audit Findings

**2022 Q1 Infrastructure Security Review (by external team)**  
Finding 1 (Critical): Coordinator process runs as root. Resolved by v1.1.0 privilege drop.  
Finding 2 (High): No capability bounding. Partially resolved by post-drop capset; full
resolution requires systemd unit with `CapabilityBoundingSet` directive.  
Finding 3 (Medium): No memory limit enforced. Deferred; systemd `MemoryMax` will address.  
Finding 4 (Low): Log files world-readable. Resolved by setting log directory permissions to 0750.  

**2024 Q1 Security Audit (internal)**  
Finding 1 (High): No systemd integration; supervision via custom script has had reliability issues.  
Finding 2 (Medium): Capability set not formally bounded before privilege drop. The capset call
after privilege drop is correct, but there is no enforced upper bound on capabilities during
the pre-drop startup window.  
Finding 3 (Low): PID file race condition (see INC-2024-0021).  
Finding 4 (Informational): Coordinator's `/proc/sys/kernel/shmmax` read access is not
documented in any security review. The access is benign (read-only, `/proc` pseudofile) and
is used for the shmmax pre-flight check documented in INC-2022-0034.  

**Audit Recommendation**: All findings from both audits will be addressed by the Q4 2024
systemd migration. The systemd unit will provide: `CapabilityBoundingSet` enforcement,
proper restart policy, `MemoryMax`, and process isolation via namespace restrictions.

---

## Section 6: OS Integration Requirements

### 6.1 Systemd Migration Goals

The systemd migration will replace the current launcher-script + monitoring-script approach
with a proper systemd service unit. The goals are:

1. **Correct startup ordering**: The coordinator must start after the network is up, after
   `/run` is writable, and after the DRM GPU device is initialized by udevd.

2. **Automatic restart**: systemd's built-in `Restart=on-failure` will replace the custom
   monitoring script, eliminating the stale-PID-file and tight-restart-loop issues
   documented in the incident history.

3. **Capability bounding**: The `CapabilityBoundingSet` directive will enforce that the
   coordinator can only ever retain `CAP_SYS_NICE` and `CAP_NET_BIND_SERVICE`, even during
   the pre-drop startup window.

4. **Proper directory management**: `tmpfiles.d` will replace the manual `mkdir` calls in
   the startup script.

5. **Environment file**: The `/etc/finchrender/environment` file will be referenced via
   `EnvironmentFile=` in the service unit, replacing the manual `source` in the launcher.

6. **Socket activation**: The coordinator socket will be managed by a companion `.socket`
   unit, enabling socket activation and clean socket lifecycle management.

### 6.2 tmpfiles.d Requirements

The systemd migration requires a `tmpfiles.d` configuration file for the coordinator's
runtime and cache directories. Based on the directory access patterns observed in the strace
and lsof sessions, the following entries are required:

**Runtime socket directory** (must exist before the coordinator starts, recreated on every
boot since `/run` is a tmpfs):
```
d  /run/finchrender  0755  finchrender  render  -
```
The `d` entry type creates the directory if it does not exist and verifies permissions on
each boot. This replaces the `mkdir -p /run/finchrender` call in the current startup script.

**Tile cache directory** (must persist across reboots; old entries should be cleaned on
boot to prevent stale tile data from being served):
```
D  /var/cache/finchrender/tiles  0750  finchrender  render  -
```
The `D` entry type creates the directory (like `d`) and additionally removes all contents
on every boot. This ensures a clean tile cache state after each coordinator restart.

**Frame buffer cache directory**:
```
D  /var/cache/finchrender/frames  0750  finchrender  render  -
```
Same semantics as the tiles directory. Frame buffer data is transient; stale frames from
a previous coordinator instance should not be served.

**Shader cache directory** (compiled shaders can be reused across reboots; however, after a
coordinator upgrade, the shader cache format may change, so clearing on boot is safer):
```
D  /var/cache/finchrender/shaders  0750  finchrender  render  -
```

All four entries use `finchrender` as the owner and `render` as the group, matching the
coordinator's runtime identity.

### 6.3 GPU Enumeration

The coordinator enumerates available GPU render devices at startup by reading the DRM sysfs
directory. This enumeration is performed before the coordinator enters its event loop.

The coordinator accesses the path `/sys/class/drm/` to list available DRM devices. This is a
read-only directory traversal of the sysfs virtual filesystem. Read access to `/sys/class/drm/`
is required for GPU enumeration at coordinator startup. The enumeration code uses `opendir`
and `readdir` to list entries, then attempts to open each device file to verify render
capability before adding it to the available device pool.

In the systemd unit configuration, the `ProtectKernelTunables=yes` directive makes many
sysfs paths read-only. The `/sys/class/drm/` path is accessible with read-only access even
with `ProtectKernelTunables=yes`, because sysfs device enumeration is treated as an
informational read, not a kernel tunable modification. No additional `ReadOnlyPaths` or
`ReadWritePaths` exceptions are required for this access.

If `ProtectKernelTunables=yes` is enabled in the service unit, the sysfs path
`/sys/class/drm/` remains readable (the protection makes sysfs tunable paths read-only, but
does not remove read access from device enumeration paths). The GPU device node itself
(`/dev/dri/renderD128`) is a character device under `/dev/`, not a sysfs path, and is handled
separately via the `DeviceAllow` directive documented in Section 5.3.

### 6.4 Privilege Drop Sequence

The coordinator handles its own privilege drop internally. The systemd unit does not use the
`User=` directive to drop privileges before exec — instead, the coordinator starts as root
(or with the `AmbientCapabilities` set) and performs `setgid`/`setuid`/`capset` internally.

However, for the systemd migration, the recommended approach is to use systemd's built-in
privilege management:

1. Set `User=finchrender` and `Group=render` in the unit file.
2. Set `AmbientCapabilities=CAP_SYS_NICE CAP_NET_BIND_SERVICE` so the coordinator process
   starts with these capabilities despite running as a non-root user.
3. Set `CapabilityBoundingSet=CAP_SYS_NICE CAP_NET_BIND_SERVICE` to enforce the upper bound.

With this configuration, the coordinator process starts directly as `finchrender:render` with
the required ambient capabilities. The coordinator's internal `setgid`/`setuid`/`capset` calls
become no-ops or benign (since the process is already running as the target user/group), but
they do not cause errors.

This approach is more secure than the current model because it eliminates the root window
entirely: the coordinator process never has root privileges, not even during startup.

### 6.5 Socket Activation

The systemd socket activation model allows the coordinator socket to be created and held by
systemd (via the `.socket` unit) before the coordinator process starts. When the coordinator
starts, it inherits the pre-created socket via the `LISTEN_FDS`/`LISTEN_PID` environment
variables (per the `sd_listen_fds(3)` protocol).

This approach has the following benefits:
- The socket exists (and can accept queued connections from the gateway and workers) even
  while the coordinator is restarting.
- Connection attempts during restart do not fail; they queue in the kernel's accept backlog.
- The socket file lifecycle is managed by systemd; there is no stale-socket-file problem.

The `.socket` unit must set `ListenStream=/run/finchrender/coordinator.sock` to create the
UNIX domain socket at the correct path.

---

## Section 7: Migration Planning Decisions

### 7.1 Capability Audit

In August 2024, AR conducted a formal capability audit as part of INFRA-0287. The goal was
to enumerate the capabilities required by the coordinator and identify any that could be
eliminated.

The audit methodology was to review the strace sessions for all `capget`, `capset`, and
`prctl` calls, cross-reference with the coordinator source code, and consult the team members
familiar with the coordinator's internal privilege model (PK and TL).

**Capabilities currently in the pre-drop set (inherited from root)**:
- `CAP_CHOWN` — change file ownership
- `CAP_DAC_OVERRIDE` — bypass file read/write/execute permission checks
- `CAP_SETGID` — make arbitrary changes to process GIDs
- `CAP_SETUID` — make arbitrary changes to process UIDs
- `CAP_SYS_NICE` — lower/raise process scheduling priority
- `CAP_NET_BIND_SERVICE` — bind to ports below 1024

The pre-drop set is the full set inherited when the coordinator starts as root. The privilege
drop sequence reduces this to the minimal post-drop set.

### 7.2 REJECTED: Retain CAP_CHOWN for Cache Directory Management

**Status: REJECTED 2024-08-12 (INFRA-0287)**

During the capability audit, PK proposed retaining `CAP_CHOWN` in the coordinator's
post-drop capability set to allow the coordinator to reset ownership on cache directory
entries if they were incorrectly created by a different process. The rationale was:

> "The coordinator's cache manager integration sometimes creates temporary files as root
> during maintenance operations. If the coordinator retained CAP_CHOWN, it could fix these
> ownership issues automatically without requiring operator intervention."

This proposal was reviewed by AR and JM and **rejected** for the following reasons:

1. `CAP_CHOWN` is a powerful capability that allows the process to set file ownership to any
   uid/gid on the system. Retaining it post-drop significantly increases the blast radius
   of a coordinator compromise.

2. The underlying problem (temporary files created as root in cache directories) should be
   fixed at the source (the cache manager maintenance mode should not run as root), not
   worked around by giving the coordinator extra capabilities.

3. The strace sessions confirm that the coordinator does not call `chown(2)`, `fchown(2)`, or
   `lchown(2)` under any observed condition, confirming that `CAP_CHOWN` is not actually
   needed for current coordinator functionality.

4. The capability audit's principle of least privilege requires that capabilities not
   demonstrably needed for current production functionality must not be retained.

**Decision**: `CAP_CHOWN` is NOT retained in the coordinator's post-drop capability set and
must NOT be included in the systemd unit's `CapabilityBoundingSet` or `AmbientCapabilities`
directives.

The cache manager maintenance mode was separately fixed to run under the `finchrender` user
identity rather than root.

### 7.3 Approved Capability Set

The approved capability set for the coordinator, confirmed by the INFRA-0287 capability audit,
is:

**Retained capabilities**: `CAP_SYS_NICE` and `CAP_NET_BIND_SERVICE` **only**.

No other capabilities are retained. The systemd unit must set:
```
CapabilityBoundingSet=CAP_SYS_NICE CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_SYS_NICE CAP_NET_BIND_SERVICE
```

`CAP_DAC_OVERRIDE`, `CAP_SETGID`, `CAP_SETUID`, and all other capabilities are dropped
entirely. Since the coordinator uses systemd's `User=/Group=` for privilege management in
the new model, `CAP_SETGID` and `CAP_SETUID` are not needed (systemd handles the identity
switch before exec). `CAP_DAC_OVERRIDE` was never needed post-drop (the filesystem
permissions are correctly set for the `finchrender` user).

### 7.4 Unit File Design Decisions

**Service unit (`finchrender.service`)**

Key decisions:
- `Type=notify` if coordinator gains systemd notify support in a future version; `Type=exec`
  for now (coordinator does not call `sd_notify`).
- `ExecStart=/usr/local/bin/finchrender-coordinator --config /etc/finchrender/coordinator.yaml
  --system /etc/finchrender/system.toml`
- `EnvironmentFile=/etc/finchrender/finchrender.env` — the `FINCHRENDER_*` variables will
  be moved from `/etc/finchrender/environment` to this path for clarity (the `.env` extension
  is the conventional name for systemd environment files in this infrastructure).
- `Restart=on-failure` with `RestartSec=5s`
- `TimeoutStartSec=30s`
- `TimeoutStopSec=30s`

**Socket unit (`finchrender.socket`)**

- `ListenStream=/run/finchrender/coordinator.sock` — binds the coordinator socket.
- `SocketUser=finchrender`, `SocketGroup=render`, `SocketMode=0660`
- `Accept=no` — the coordinator handles accept itself (not per-connection activation).

**Environment file (`finchrender.env`)**

Replaces `/etc/finchrender/environment`. Contains the four `FINCHRENDER_*` variables:
```
FINCHRENDER_TILE_WORKERS=8
FINCHRENDER_FRAME_BUFFER_MB=512
FINCHRENDER_SOCKET_TIMEOUT=30
FINCHRENDER_LOG_LEVEL=info
```

**tmpfiles.d configuration (`finchrender-tmpfiles.conf`)**

As documented in Section 6.2.

---

## Section 8: Capacity Planning

### 8.1 Current Capacity Profile

The current deployment (prod-render-01 through prod-render-14) handles approximately 8,000
render-hours per day. Peak load occurs during the 16:00-23:00 UTC window (production deadline
crunch time). During peak hours, the coordinator queue depth can reach 800-1,200 pending
tile-dispatch requests.

The coordinator's single-threaded event loop handles up to 14 worker connections simultaneously.
With `FINCHRENDER_TILE_WORKERS=8`, up to 8 concurrent tile-dispatch operations can be in
flight. The event loop processes approximately 1,200 events per second at peak load, which
is well within the coordinator's designed capacity (event loop benchmarks indicate 50,000
events/second as the upper bound on the coordinator host's hardware).

### 8.2 Worker Node Capacity

Each worker node (render-capable GPU workstation):
- CPU: 32 cores (AMD EPYC 7351)
- RAM: 128 GB
- GPU: Single NVIDIA RTX 4090 (for render compute)
- GPU VRAM: 24 GB
- Storage: 2 TB NVMe (local scratch) + 10 TB spinning (persistent cache)
- Network: 25 GbE (for frame data transfer)

The coordinator host has a different profile optimized for coordination rather than render:
- CPU: 16 cores (Intel Xeon W-2195)
- RAM: 64 GB
- GPU: AMD Radeon Pro WX 7100 (for thumbnail and pre-processing only)
- Storage: 1 TB NVMe (OS and coordinator state) + 4 TB NVMe (coordinator cache)
- Network: 10 GbE

### 8.3 Cache Capacity Planning

Tile cache (`/var/cache/finchrender/tiles`): Current usage averages 280 GB with peaks of
420 GB at end-of-day. The LRU eviction policy is configured with a 500 GB ceiling.

Frame buffer cache (`/var/cache/finchrender/frames`): Current usage averages 150 GB with
peaks of 350 GB during batch render runs. The LRU eviction policy is configured with a 400 GB ceiling.

Shader cache (`/var/cache/finchrender/shaders`): Current usage is 22 GB and grows slowly
as new shader programs are compiled. There is no active eviction for the shader cache; it is
cleared on coordinator restart (version boundary) via the `tmpfiles.d D` directive.

### 8.4 Growth Projections (Q4 2024 — Q4 2025)

Based on the 12-month growth trend in render job volume (+35% year-over-year), the following
capacity additions are projected:

- **Q1 2025**: Two additional render nodes (prod-render-15, prod-render-16). The coordinator
  can handle up to 32 workers without code changes; worker registration logic scales linearly.

- **Q2 2025**: Cache storage expansion for the coordinator host (+8 TB NVMe). Current growth
  rate of tile cache (+15 GB/month) will require capacity by Q2 2025.

- **Q3 2025**: Coordinator host CPU upgrade if event loop throughput reaches 80% of benchmark
  maximum (currently at 42%).

- **Q4 2025**: Evaluate multi-coordinator sharding if worker count approaches the per-coordinator
  limit. Current limit is 32 workers (code-configurable); hardware limit (FD table, event loop
  latency) is estimated at ~128 workers per coordinator instance.

### 8.5 Network Capacity

Peak network throughput on the coordinator host is approximately 1.8 Gbps during batch render
completion bursts (when multiple workers simultaneously return assembled frames). The 10 GbE
link is not currently a bottleneck. If the planned Q1 2025 scale-out proceeds, a link
upgrade to 25 GbE should be evaluated.

Coordinator-to-worker IPC traffic (via UNIX socket, local to each worker host) is not a
bottleneck since it is inherently bounded by the single-host loopback bandwidth.

### 8.6 Memory Capacity

The coordinator's memory profile:
- Static: ~45 MB (coordinator binary + loaded libraries)
- Job queue: ~1 MB per 1,000 queued tile-dispatch requests (each request is ~1 KB of metadata)
- Frame buffer: up to 512 MB (`FINCHRENDER_FRAME_BUFFER_MB=512`, current setting)
- Worker state: ~4 KB per connected worker (~56 KB for 14 workers)
- Socket buffers: ~256 KB per connected socket (kernel-managed; ~4 MB for 14 workers + listener)

Total expected peak RSS: 600-700 MB. The current coordinator host has 64 GB RAM; memory is
not a current concern. The systemd unit will set `MemoryMax=4G` as a safety ceiling.

---

## Section 9: Pre/Post Upgrade Validation Procedures

### 9.1 Pre-Upgrade Checklist

Before upgrading the coordinator binary or configuration:

1. **Verify worker count**: Confirm all 14 workers are registered and healthy.
   Check: `curl -s http://localhost:9090/metrics | grep frc_workers_connected`
   Expected: `frc_workers_connected 14`

2. **Drain in-flight jobs**: For major upgrades (minor/patch upgrades can proceed without drain),
   pause new job submissions from the gateway and wait for the queue to drain.
   Check: `curl -s http://localhost:9090/metrics | grep frc_jobs_queued`
   Expected: `frc_jobs_queued 0`

3. **Checkpoint state**: Verify the checkpoint directory is accessible and the last checkpoint
   file is less than 5 minutes old.
   Check: `ls -lt /var/lib/finchrender/checkpoints/ | head -5`

4. **Verify shmmax**: `cat /proc/sys/kernel/shmmax`
   Expected: `>= 67108864` (64 MB)

5. **Verify cache directory ownership**: 
   ```bash
   stat -c '%U:%G %a' /var/cache/finchrender/tiles                        /var/cache/finchrender/frames                        /var/cache/finchrender/shaders
   ```
   Expected: `finchrender:render 750` for each directory.

6. **Verify GPU device permissions**:
   `stat -c '%U:%G %a' /dev/dri/renderD128`
   Expected: `root:render 660`

7. **Verify coordinator binary**: `md5sum /usr/local/bin/finchrender-coordinator`
   Compare against the release artifact hash in the release notes.

8. **Backup current config files**: 
   ```bash
   cp /etc/finchrender/coordinator.yaml /etc/finchrender/coordinator.yaml.bak.$(date +%Y%m%d)
   cp /etc/finchrender/system.toml /etc/finchrender/system.toml.bak.$(date +%Y%m%d)
   ```

### 9.2 Post-Upgrade Validation

After starting the upgraded coordinator:

1. **Verify process started**: `pgrep -x finchrender-coordinator`
   Expected: one PID

2. **Verify identity**: `cat /proc/$(pgrep -x finchrender-coordinator)/status | grep -E 'Uid|Gid'`
   Expected: `Uid: 2771 2771 2771 2771` and `Gid: 2001 2001 2001 2001`

3. **Verify capability set**: `cat /proc/$(pgrep -x finchrender-coordinator)/status | grep Cap`
   Expected: `CapEff` and `CapPrm` should decode to exactly `CAP_SYS_NICE|CAP_NET_BIND_SERVICE`.

4. **Verify socket**: `stat /run/finchrender/coordinator.sock`
   Expected: socket file exists, owned by `finchrender:render`, permissions `0660`.

5. **Verify worker reconnection**: Wait 60 seconds, then check worker count metric.
   Expected: `frc_workers_connected 14` (all workers reconnected)

6. **Verify cache directories still accessible**:
   `ls /var/cache/finchrender/tiles /var/cache/finchrender/frames /var/cache/finchrender/shaders`
   Expected: directories list successfully (as the operator, these should be readable by root)

7. **Submit a test render job**: Submit one tile-level test job via the gateway API.
   Expected: job completes within 30 seconds, tile appears in the tiles cache.

8. **Check for errors**: `journalctl -u finchrender -n 100 --no-pager | grep -iE 'error|fatal|warn'`
   Expected: no unexpected errors or warnings.

### 9.3 Rollback Procedure

If the upgrade reveals a critical issue:

1. Stop the upgraded coordinator: `systemctl stop finchrender` (or kill if not yet on systemd)
2. Restore the binary backup: `cp /usr/local/bin/finchrender-coordinator.bak.$(date +%Y%m%d) /usr/local/bin/finchrender-coordinator`
3. Restore config backups: `cp /etc/finchrender/coordinator.yaml.bak.$(date +%Y%m%d) /etc/finchrender/coordinator.yaml`
4. Start the previous version
5. Verify worker reconnection and job processing resume within 5 minutes
6. File a rollback incident report within 24 hours

---

## Section 10: Configuration Glossary

**`FINCHRENDER_TILE_WORKERS`** (integer, default: 4)  
Number of concurrent tile-dispatch worker goroutines in the coordinator's internal thread pool.
Increasing this value allows more tiles to be dispatched to render workers simultaneously but
increases the coordinator's CPU usage. Set to 8 in the current production configuration.

**`FINCHRENDER_FRAME_BUFFER_MB`** (integer, default: 256)  
Size of the in-memory frame assembly buffer in megabytes. The coordinator assembles individual
tiles into complete frames in this buffer before writing to the frame cache directory. Must be
large enough to hold the largest expected frame. Set to 512 MB in the current production
configuration to accommodate 4K HDR frames.

**`FINCHRENDER_SOCKET_TIMEOUT`** (integer, default: 60)  
Idle timeout for worker connections in seconds. If a worker does not send any message for this
duration, the coordinator closes the connection and marks the worker as offline. Set to 30
seconds in the current production configuration to quickly detect stale connections.

**`FINCHRENDER_LOG_LEVEL`** (string, default: warn)  
Logging verbosity level. Valid values: `debug`, `info`, `warn`, `error`. Higher verbosity
produces more log output and may impact coordinator performance under heavy load. Set to
`info` in the current production configuration to provide operational visibility while
keeping log volume manageable.

**`tile_workers`** (coordinator.yaml)  
Same as `FINCHRENDER_TILE_WORKERS`. If both are set, the environment variable takes precedence.

**`frame_buffer_mb`** (coordinator.yaml)  
Same as `FINCHRENDER_FRAME_BUFFER_MB`. If both are set, the environment variable takes precedence.

**`socket_timeout`** (coordinator.yaml)  
Same as `FINCHRENDER_SOCKET_TIMEOUT`. If both are set, the environment variable takes precedence.

**`log_level`** (coordinator.yaml)  
Same as `FINCHRENDER_LOG_LEVEL`. If both are set, the environment variable takes precedence.

**`socket_path`** (coordinator.yaml)  
Path to the coordinator's UNIX socket. Default: `/run/finchrender/coordinator.sock`. This
value should not be changed in production without updating all worker node configurations
to use the new path.

**`pid_file`** (coordinator.yaml)  
Path to the coordinator's PID file. Default: `/run/finchrender/coordinator.pid`. Written at
startup after privilege drop. Used by the monitoring script for liveness checking. Will be
deprecated when systemd migration is complete.

**`tiles_dir`** (coordinator.yaml)  
Path to the tile cache directory. Default: `/var/cache/finchrender/tiles`. Must be owned by
`finchrender:render` with mode 0750 or more permissive.

**`frames_dir`** (coordinator.yaml)  
Path to the frame buffer cache directory. Default: `/var/cache/finchrender/frames`. Same
ownership requirements as `tiles_dir`.

**`shaders_dir`** (coordinator.yaml)  
Path to the compiled shader cache directory. Default: `/var/cache/finchrender/shaders`. Same
ownership requirements as `tiles_dir`.

**`max_workers`** (coordinator.yaml)  
Maximum number of simultaneously connected worker nodes. Default: 8. Currently set to 16 to
provide headroom above the 14 active workers. The coordinator will reject registration attempts
from workers that would exceed this limit.

**`min_workers`** (node-pool.yaml)  
Minimum number of worker nodes that must be registered before the coordinator will accept
job submissions. Currently set to 2. If the registered worker count drops below this value,
the coordinator suspends the job submission gateway's accept loop and alerts.

---

## Section 11: Node Pool Specifications

### 11.1 Current Node Pool

The render node pool consists of 14 nodes (prod-render-01 through prod-render-14). All nodes
run the same OS image (Debian Bookworm 12, kernel 6.1.0-21) and the same coordinator worker
version (v2.0.4).

Nodes are divided into two generations:
- **Generation 1** (prod-render-01 through prod-render-08): Original nodes, deployed 2022.
  GPU: NVIDIA RTX 3090. Performance: ~1.8 GPU-hours per wall-clock hour.
- **Generation 2** (prod-render-09 through prod-render-14): Newer nodes, deployed 2023.
  GPU: NVIDIA RTX 4090. Performance: ~3.1 GPU-hours per wall-clock hour.

Total theoretical peak capacity: 8 × 1.8 + 6 × 3.1 = 33.0 GPU-hours per wall-clock hour.
With scheduling overhead and typical utilisation of 85%, effective capacity is approximately
28 GPU-hours per wall-clock hour.

### 11.2 Worker Registration Protocol

When a worker node starts, the `finchrender-worker` process connects to the coordinator's
UNIX socket and sends a `REGISTER` message containing:
- Worker hostname (e.g., `prod-render-07`)
- Worker version string (e.g., `2.0.4`)
- GPU model (from `/sys/class/drm/` enumeration)
- Available VRAM (from GPU driver query)
- Available CPU cores

The coordinator acknowledges registration and assigns the worker a worker ID. The coordinator
maintains the worker state table in memory. Workers send a heartbeat every 30 seconds; the
coordinator marks a worker as offline if no heartbeat is received within the
`FINCHRENDER_SOCKET_TIMEOUT` window (30 seconds).

### 11.3 Job Dispatch Protocol

When a render job is submitted to the coordinator:
1. The coordinator decomposes the job into tiles (each tile is a sub-region of one frame).
2. For each tile, a `DISPATCH_TILE` message is sent to an available worker.
3. The worker renders the tile and sends a `TILE_COMPLETE` message with the output path.
4. The coordinator records the completion and assembles frames when all tiles for a frame
   are complete.
5. Completed frames are written to `/var/cache/finchrender/frames/`.
6. The coordinator sends a `JOB_COMPLETE` message to the gateway.

### 11.4 Worker Failure Handling

If a worker fails to complete a tile within the configured timeout (default: 300 seconds), the
coordinator marks the tile as failed and retries it on a different worker. Maximum retry count
is 3 (configured in `jobqueue.toml`). If all 3 retries fail, the job is marked as failed and
the submitter is notified via the gateway.

### 11.5 Worker Drain Procedure

To remove a worker node from the pool for maintenance:
1. Send a `DRAIN_WORKER <hostname>` command to the coordinator via the management socket.
2. The coordinator stops dispatching new tiles to the target worker.
3. Wait for in-flight tiles to complete (monitor via metrics: `frc_worker_inflight_tiles{worker="<hostname}"}`).
4. Once in-flight count reaches 0, the worker can be safely shut down.

The coordinator will automatically close the worker's connection when the worker process exits.

### 11.6 Node Pool Monitoring

Each worker node runs a Prometheus node exporter, and the coordinator's built-in exporter
surfaces per-worker metrics:

| Metric | Description |
|--------|-------------|
| `frc_worker_status{worker}` | 1=connected, 0=offline |
| `frc_worker_inflight_tiles{worker}` | Active tile renders on this worker |
| `frc_worker_render_latency_ms{worker}` | Tile render time p50/p95/p99 |
| `frc_worker_heartbeat_age_sec{worker}` | Seconds since last heartbeat |

---

## Section 12: Job Queue Schema Reference

### 12.1 Job Submission Format

Jobs are submitted to the coordinator via the gateway, which translates the REST API request
into an IPC message in the coordinator's job submission format. The coordinator internally
uses a binary protocol over the UNIX socket, but the gateway presents jobs in JSON format to
the REST API consumers.

**Job Submission JSON Schema**:
```json
{
  "job_id": "string (UUID, assigned by gateway)",
  "scene_package": "string (path to scene bundle on shared storage)",
  "output_bucket": "string (path for output frames on shared storage)",
  "frame_range": {
    "start": "integer",
    "end": "integer",
    "step": "integer (default: 1)"
  },
  "render_settings": {
    "resolution_x": "integer",
    "resolution_y": "integer",
    "samples": "integer (anti-aliasing samples, default: 512)",
    "denoise": "boolean (enable AI denoising, default: true)"
  },
  "priority": "integer (1=low, 2=medium, 3=high, default: 2)",
  "submitter": "string (authenticated user identity)"
}
```

### 12.2 Job State Machine

```
QUEUED → DISPATCHING → IN_FLIGHT → ASSEMBLING → COMPLETE
              ↓                ↓
           FAILED          RETRYING (max 3 retries)
              ↑                ↓
              └────────────────┘
```

State transitions are atomic within the coordinator's event loop. No partial state is visible
to external observers; the gateway receives either a `JOB_QUEUED` acknowledgement or a
`JOB_FAILED` notification.

### 12.3 Tile Decomposition

The coordinator decomposes each frame into tiles based on the configured tile size (default:
256×256 pixels). For a 4K frame (3840×2160), the tile decomposition produces:
- Horizontal tiles: ceil(3840 / 256) = 15 tiles
- Vertical tiles: ceil(2160 / 256) = 9 tiles
- Total tiles per frame: 135 tiles

With `FINCHRENDER_TILE_WORKERS=8`, up to 8 tiles can be in-flight simultaneously. For a
135-tile frame at an average render time of 45 seconds per tile, the expected frame completion
time is approximately ceil(135 / 8) × 45 = 780 seconds (13 minutes).

### 12.4 Checkpoint Format

Checkpoint files are written to `/var/lib/finchrender/checkpoints/` in a binary format. Each
checkpoint file covers one job and records the completion status of each tile. The file naming
convention is: `{job_id}.checkpoint`.

Checkpoint files are written incrementally (each tile completion updates the checkpoint file),
and are read at coordinator startup to resume in-progress jobs after a restart. Checkpoint
files are garbage-collected 7 days after job completion.

### 12.5 Queue Priority

The job queue uses a priority queue with 3 priority levels (low=1, medium=2, high=3). Within
the same priority level, jobs are dispatched in FIFO order. High-priority jobs preempt queued
(but not in-flight) medium and low-priority tiles.

The maximum queue depth is 1,000 jobs (configured in `jobqueue.toml`). If the queue is full,
the gateway returns a `503 Service Unavailable` response to the submitter.

### 12.6 Retry Configuration

From `jobqueue.toml`:
```toml
[retry]
max_attempts = 3
backoff_base_sec = 5
backoff_max_sec = 120
```

Retry backoff is exponential: first retry after 5 seconds, second after 25 seconds, third
after 125 seconds (capped at 120 seconds). If all 3 retries exhaust, the tile (and therefore
the job) is marked as permanently failed.

---

## Section 13: Runbooks

### 13.1 Graceful Reload Procedure

The coordinator supports graceful reload via SIGHUP. During a graceful reload:
1. The coordinator forks a new child process (the "successor")
2. The successor performs the full startup sequence (config read, privilege drop, socket bind
   or socket inheritance, cache opens)
3. Once the successor signals readiness, the parent begins draining in-flight tiles
4. The parent sends `MIGRATING` notifications to all connected workers, causing them to
   complete current tiles but not accept new ones
5. The parent sends a socket handover message to the successor
6. The parent exits once all in-flight tiles complete

**Procedure**:
1. Verify current coordinator is healthy: check metrics, verify worker count.
2. Apply config changes (if any).
3. Send SIGHUP: `systemctl kill -s HUP finchrender` (or `kill -HUP $(pgrep finchrender-coordinator)`)
4. Monitor logs for "graceful reload initiated" and "handover complete" messages.
5. Expected completion time: 30-90 seconds (depends on in-flight tile count).

**On failure**: If the successor fails to start (startup error), the parent process continues
running with the original configuration. The SIGHUP reload is designed to be atomic from the
perspective of external clients.

### 13.2 Emergency Restart Procedure

For cases where the coordinator must be restarted without draining (e.g., after a crash or
when processing is hung):

1. **Stop the current coordinator**:
   - Via systemd (after migration): `systemctl stop finchrender`
   - Legacy: `kill -TERM $(pgrep -x finchrender-coordinator)` (graceful) or
     `kill -KILL $(pgrep -x finchrender-coordinator)` (force kill)

2. **Verify shutdown**: `pgrep -x finchrender-coordinator` should return nothing.

3. **Check for stale socket**: `stat /run/finchrender/coordinator.sock`
   - If the socket file exists and no coordinator is running, remove it:
     `rm /run/finchrender/coordinator.sock`
   - With systemd socket activation, this step is not needed (systemd manages the socket).

4. **Check for stale PID file**: `cat /run/finchrender/coordinator.pid`
   - If the PID is not running: `rm /run/finchrender/coordinator.pid`
   - With systemd, this step is not needed.

5. **Start coordinator**:
   - Via systemd (after migration): `systemctl start finchrender`
   - Legacy: `/usr/local/bin/finchrender-launcher`

6. **Verify startup**: Check logs for "coordinator started" message. Verify socket exists.

7. **Verify worker reconnection**: Wait 60 seconds, check `frc_workers_connected` metric.

8. **Resume job submissions**: If submissions were paused, re-enable via gateway config.

**Note on in-progress jobs**: Any tiles that were in-flight when the coordinator crashed will
not be resumed automatically (unless the workers detect the coordinator connection loss and
report the tiles back as failed). The coordinator's checkpoint mechanism allows it to identify
which tiles were in-progress at restart and re-dispatch them.

### 13.3 Worker Pool Drain Procedure

To drain a specific worker node (e.g., for hardware maintenance):

1. **Initiate drain via management command**:
   ```
   finchrender-ctl drain-worker prod-render-07
   ```
   This sends a `DRAIN_WORKER` command to the coordinator via the management socket.

2. **Monitor drain progress**:
   ```bash
   watch 'curl -s http://localhost:9090/metrics | grep frc_worker_inflight_tiles{worker="prod-render-07"}'
   ```
   Wait until the value reaches 0.

3. **Confirm worker is idle**: The coordinator will log "worker prod-render-07 drained" when
   the drain is complete.

4. **Shut down the worker node**: Stop the `finchrender-worker` service on the target node.
   The coordinator will detect the connection closure and mark the worker as offline.

5. **Perform maintenance** on the node.

6. **Restore the worker**: Start `finchrender-worker` on the target node. It will register
   automatically with the coordinator within 30 seconds.

7. **Verify reconnection**: Check `frc_worker_status{worker="prod-render-07"}` metric.

**Warning**: Do not forcibly kill the worker process while tiles are in-flight without first
draining. In-flight tiles will be retried by the coordinator after the worker connection drops,
but this adds unnecessary retry latency to affected jobs.

### 13.4 Cache Prune Procedure

The cache directories are managed by the `finchrender-cache` process. Manual intervention
is rarely needed, but if the cache exceeds its configured ceiling due to an eviction failure:

1. **Check cache usage**:
   ```bash
   du -sh /var/cache/finchrender/{tiles,frames,shaders}
   ```

2. **Identify old entries** (files not accessed in the last 7 days):
   ```bash
   find /var/cache/finchrender/tiles -atime +7 -type f -ls | sort -k 7 -n | head -50
   ```

3. **Manual prune** (as finchrender user or root; verify ownership before deleting):
   ```bash
   find /var/cache/finchrender/tiles -atime +7 -type f -delete
   ```
   **Important**: Verify directory ownership before running this command:
   ```bash
   stat -c '%U:%G %a' /var/cache/finchrender/tiles
   ```
   Expected: `finchrender:render 750`

4. **Force cache manager rescan** (send SIGUSR1 to the cache manager):
   ```bash
   kill -USR1 $(pgrep -x finchrender-cache)
   ```

5. **Verify post-prune usage**: Repeat step 1.

**Warning**: Do not run cache prune commands as root without verifying ownership first. See
INC-2022-0019 for the consequences of incorrect post-prune ownership.

---

## Appendix A: Network Topology

The coordinator and all render nodes are on the `10.100.0.0/16` internal network segment.
The coordinator host's IP is `10.100.1.10`. Worker nodes are in the `10.100.2.0/24` range:

| Hostname | IP Address | Generation | GPU | Status |
|----------|-----------|-----------|-----|--------|
| prod-render-01 | 10.100.2.1 | 1 | RTX 3090 | Active |
| prod-render-02 | 10.100.2.2 | 1 | RTX 3090 | Active |
| prod-render-03 | 10.100.2.3 | 1 | RTX 3090 | Active |
| prod-render-04 | 10.100.2.4 | 1 | RTX 3090 | Active |
| prod-render-05 | 10.100.2.5 | 1 | RTX 3090 | Active |
| prod-render-06 | 10.100.2.6 | 1 | RTX 3090 | Active |
| prod-render-07 | 10.100.2.7 | 1 | RTX 3090 | Active |
| prod-render-08 | 10.100.2.8 | 1 | RTX 3090 | Active |
| prod-render-09 | 10.100.2.9 | 2 | RTX 4090 | Active |
| prod-render-10 | 10.100.2.10 | 2 | RTX 4090 | Active |
| prod-render-11 | 10.100.2.11 | 2 | RTX 4090 | Active |
| prod-render-12 | 10.100.2.12 | 2 | RTX 4090 | Active |
| prod-render-13 | 10.100.2.13 | 2 | RTX 4090 | Active |
| prod-render-14 | 10.100.2.14 | 2 | RTX 4090 | Active |

The coordinator host is not on the `10.100.2.0/24` segment; it is on `10.100.1.0/24`. Worker
connections to the coordinator go via the 10 GbE switch that interconnects both segments.
All worker-to-coordinator IPC goes over the 10 GbE network but is still via UNIX sockets when
the connection is on the coordinator host itself (the gateway, which runs on the same host as
the coordinator, uses the UNIX socket directly).

The gateway service is accessible from the artist network (`10.200.0.0/16`) via HTTPS (port
443) on the coordinator host. There is a Nginx reverse proxy on the coordinator host that
terminates TLS and forwards to the gateway service on `127.0.0.1:8080`.

The coordinator itself has no TCP listeners and is not accessible from the artist network or
the internet.

---

## Appendix B: Metrics Reference

The coordinator exposes Prometheus metrics on `http://localhost:9090/metrics` (loopback only).

### Process Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `frc_uptime_seconds` | gauge | Seconds since coordinator start |
| `frc_version_info{version}` | gauge | Coordinator version (label) |
| `frc_open_fds` | gauge | Current open file descriptor count |

### Job Queue Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `frc_jobs_queued{priority}` | gauge | Current queue depth by priority |
| `frc_jobs_dispatched_total{priority}` | counter | Total jobs dispatched since start |
| `frc_jobs_completed_total` | counter | Total jobs completed successfully |
| `frc_jobs_failed_total{reason}` | counter | Total jobs that failed, by reason |
| `frc_job_queue_wait_seconds` | histogram | Time from submission to first tile dispatch |
| `frc_job_completion_seconds` | histogram | Total job wall-clock time |

### Worker Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `frc_workers_connected` | gauge | Total registered+connected workers |
| `frc_worker_status{worker}` | gauge | 1=connected, 0=offline, per worker |
| `frc_worker_inflight_tiles{worker}` | gauge | Active tile renders per worker |
| `frc_worker_render_latency_seconds{worker,quantile}` | summary | Tile render latency per worker |
| `frc_worker_heartbeat_age_seconds{worker}` | gauge | Seconds since last heartbeat |
| `frc_worker_retries_total{worker}` | counter | Total tile retries on this worker |

### Cache Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `frc_cache_hit_ratio{cache}` | gauge | Cache hit ratio for tiles/frames/shaders |
| `frc_cache_size_bytes{cache}` | gauge | Current cache size in bytes |
| `frc_cache_evictions_total{cache}` | counter | Total cache evictions |

### IPC Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `frc_socket_accept_total` | counter | Total accepted connections on coordinator socket |
| `frc_socket_accept_latency_seconds` | histogram | Time from select() ready to accept() return |
| `frc_socket_queue_depth` | gauge | Current kernel accept queue depth |

---

## Appendix C: Alert Definitions

Alerts are configured in PagerDuty with routing to the on-call platform engineer.

### P1 Alerts (Immediate Response Required)

**CoordinatorDown**  
Condition: `up{job="finchrender"} == 0` for 2 minutes  
Description: The coordinator process is not responding to metric scrapes.  
Action: Follow Section 13.2 (Emergency Restart Procedure).

**AllWorkersOffline**  
Condition: `frc_workers_connected == 0` for 5 minutes  
Description: No workers are connected; render farm is completely offline.  
Action: Check worker node status; verify coordinator socket is accessible.

### P2 Alerts (Response Within 15 Minutes)

**WorkerCountCritical**  
Condition: `frc_workers_connected < 6` for 5 minutes  
Description: More than 8 workers are offline; render capacity severely degraded.  
Action: Check worker node status via Grafana; initiate worker restart if needed.

**QueueDepthCritical**  
Condition: `sum(frc_jobs_queued) > 2000` for 10 minutes  
Description: Job queue is more than twice the normal maximum, suggesting dispatch stall.  
Action: Check coordinator logs; verify workers are receiving dispatch messages.

**FdCountHigh**  
Condition: `frc_open_fds > 50` for 5 minutes  
Description: Coordinator file descriptor count is above normal operating range.  
Action: Check for FD leak (see INC-2024-0033 for historical precedent).

### P3 Alerts (Response Within 1 Hour)

**WorkerCountDegraded**  
Condition: `frc_workers_connected < 10` for 15 minutes  
Description: Several workers offline; capacity degraded but operational.

**CacheHitRatioLow**  
Condition: `frc_cache_hit_ratio{cache="tiles"} < 0.5` for 10 minutes  
Description: Tile cache hit ratio is low; renders may be slower than expected.

**QueueDepthHigh**  
Condition: `sum(frc_jobs_queued) > 800` for 15 minutes  
Description: Job queue depth above normal peak; may indicate submission rate spike.

**WorkerRenderLatencyHigh**  
Condition: `frc_worker_render_latency_seconds{quantile="0.95"} > 300` for 10 minutes  
Description: 95th percentile tile render time exceeds 5 minutes (baseline: ~45 seconds).

### Alert Routing

| Severity | Primary On-Call | Escalation (if no ACK in 15 min) |
|----------|----------------|----------------------------------|
| P1 | Platform On-Call | Platform Lead + VFX Pipeline Lead |
| P2 | Platform On-Call | Platform Lead |
| P3 | Platform On-Call | No automatic escalation |

Alerts are suppressed during declared maintenance windows. Maintenance windows are declared
in PagerDuty at least 30 minutes in advance. During maintenance windows, P3 alerts are
automatically silenced; P1 and P2 alerts are still active.

---

*End of Document*

*For questions about this document, contact the Platform Engineering team via the
`#platform-infra` Slack channel or open an INFRA ticket.*


---

## Section 14: Detailed Incident Timeline and Root Cause Analysis

This section provides expanded post-mortem analysis for the incidents documented in Section 3.2.
It is intended for engineers onboarding to the platform who need deeper context than the
incident report summaries provide, and for the systemd migration team who should understand
what failure modes the migration is designed to eliminate.

### 14.1 Expanded Analysis: INC-2022-0012 (Coordinator Startup Race)

**Background**

The coordinator's dependency on `/run/finchrender/` existing before it starts is a fundamental
design constraint. The `/run` filesystem on Linux is typically a `tmpfs` that is created fresh
on every boot by the init system. Under `rc.local`-based init (pre-systemd integration), there
was no formal mechanism to express ordering dependencies between init script phases and tmpfs
population.

The specific sequence of events in INC-2022-0012 was:
1. Host reboots (kernel upgrade, scheduled maintenance window 02:00-03:00 UTC)
2. `/run` tmpfs is mounted at approximately T+0:05
3. systemd (running alongside `rc.local`) starts its internal units at T+0:06
4. The `rc.local` compatibility service starts at T+0:08
5. `rc.local` contains `/usr/local/bin/finchrender-launcher &` which starts the coordinator
6. At T+0:08, `/run/finchrender/` does NOT yet exist (it is created later in the boot sequence
   by a separate `setup-coordinator-dirs.sh` script invoked from a different `rc.local` entry)
7. The coordinator attempts `bind(5, {AF_UNIX, "/run/finchrender/coordinator.sock"}, 48)` and
   gets `ENOENT` because the parent directory does not exist
8. The coordinator exits with code 1
9. The monitoring script detects the failure and attempts to restart at T+0:38
10. By T+0:38, `/run/finchrender/` has been created (by the setup script which ran at T+0:12)
11. The coordinator starts successfully on the second attempt

The 12-minute window of unavailability was due to the 10-minute restart delay in the monitoring
script. The immediate fix (lowering the monitoring restart delay to 30 seconds) prevented the
12-minute outage from recurring, but did not address the root cause.

**Why This Cannot Happen With systemd**

With a proper systemd integration:
1. The `finchrender-tmpfiles.conf` entry `d /run/finchrender ...` is processed by
   `systemd-tmpfiles-setup.service` early in the boot sequence, before any application units start.
2. The `finchrender.service` unit specifies `After=systemd-tmpfiles-setup.service` implicitly
   (via `DefaultDependencies=yes`), ensuring the coordinator never starts before tmpfiles are set up.
3. The `finchrender.socket` unit creates the socket *before* the coordinator starts, so there
   is no window where the coordinator's bind fails due to a missing directory.

The incident history here is directly relevant to the systemd migration requirements: the
`tmpfiles.d` integration is not just a convenience — it eliminates a class of boot-time
startup failures that affected production twice (INC-2022-0012 and INC-2024-0055).

---

### 14.2 Expanded Analysis: INC-2022-0034 (OOM Kill and Shmmax Discovery)

**Background**

The shared memory issue in INC-2022-0034 introduced a permanent operational requirement that
is easy to overlook: the coordinator reads `/proc/sys/kernel/shmmax` at startup as a pre-flight
validation step, and this open file descriptor is held throughout the coordinator's lifetime in
the steady-state lsof capture (fd 9: `/proc/sys/kernel/shmmax`).

**Why the fd is held open**

The coordinator does not just read and close the file. It holds the file descriptor open as
part of a periodic health-check mechanism introduced in coordinator v1.4.0. Every 5 minutes,
the coordinator re-reads the shmmax value and compares it against the threshold required for
the current frame-buffer configuration. This is a defense-in-depth measure: if an operator
changes the kernel parameter while the coordinator is running, the coordinator will log a
warning and reduce the frame buffer allocation to avoid OOM conditions.

The re-read is done via `lseek(fd, 0, SEEK_SET)` followed by `read(fd, ...)` — using the
already-open file descriptor. This is why the fd appears as open in the steady-state lsof
output (fd 9) rather than being opened and closed once during startup.

For the systemd unit configuration, this means `/proc/sys/kernel/shmmax` must be accessible
to the coordinator throughout its runtime, not just at startup. Since `/proc` is a read-only
virtual filesystem (from the coordinator's perspective), no special `ReadWritePaths` is
needed — `ReadOnlyPaths=/proc` (or the default behavior of `ProtectKernelTunables=yes`) is
sufficient. The key requirement is that `/proc/sys/kernel/shmmax` must not be inaccessible
to the coordinator process.

---

### 14.3 Expanded Analysis: INC-2024-0033 (FD Leak and the 15-FD Bound)

**Background**

The FD leak in INC-2024-0033 is the incident that produced the definitive documentation of
the coordinator's expected FD profile. Before this incident, there was no formal documentation
of the expected FD count. The investigation by PK established the baseline of 13 FDs in
steady state and 15 FDs under load, which is now the authoritative figure used in monitoring
alerts and migration planning.

**How the FD count was established**

After applying the v2.0.3 hotfix, PK ran multiple `lsof -p $(pgrep finchrender-coordinator)`
captures at different times during a normal production day:

| Time | FD Count | Notes |
|------|---------|-------|
| 09:15 | 13 | No active worker connections (night-shift pause) |
| 10:30 | 15 | 2 active worker job connections |
| 12:00 | 15 | 2 active worker job connections |
| 14:45 | 15 | 2 active worker job connections (peak jobs) |
| 16:00 | 15 | 2 active worker job connections |
| 20:00 | 14 | 1 active worker job connection |
| 22:30 | 13 | No active worker connections |

The consistent maximum of 15 FDs (13 baseline + 2 worker connections at peak during this
session) established the `≤ 15` bound. Subsequent captures on different days have never
exceeded 15 FDs (at the observer-side production load level of the lsof session). Under
maximum theoretical load (14 workers all simultaneously active), the FD count would be
13 + 14 = 27, but in practice not all workers have active tile operations simultaneously,
and the `FINCHRENDER_SOCKET_TIMEOUT=30` ensures idle connections are closed promptly.

**Monitoring implications**

The Prometheus `frc_open_fds` metric was added specifically because of this incident. The
alert threshold of 50 (see Appendix C) provides significant headroom above the 15-FD
steady-state maximum, designed to catch a slow FD leak long before it reaches the system
limit (256 was the pre-incident ulimit; after the incident, this was raised to 1024).

---

### 14.4 Expanded Analysis: INC-2024-0021 (PID File Race and Systemd)

**Background**

INC-2024-0021 was the incident that directly triggered the formal approval of the systemd
migration initiative. Prior to this incident, the systemd migration had been discussed as a
"would be nice" improvement. After the incident, it was formally scoped and scheduled.

The coordinator's PID file mechanism is a well-known antipattern. The `coordinator.pid` file
is written after the coordinator completes its startup sequence (config load, privilege drop,
socket bind). If the coordinator exits abnormally (SIGSEGV, SIGKILL, OOM kill), the PID file
is not cleaned up. On the next start attempt, the monitoring script reads the PID file and
checks whether the listed PID is running:

```bash
if [ -f /run/finchrender/coordinator.pid ]; then
    pid=$(cat /run/finchrender/coordinator.pid)
    if kill -0 "$pid" 2>/dev/null; then
        echo "Coordinator already running (pid=$pid)"
        exit 0
    fi
fi
```

The `kill -0` check sends no signal; it only tests whether the process exists. After a crash,
the PID in the file is no longer active, so `kill -0` returns non-zero — and the monitoring
script should proceed to start. In INC-2024-0021, the issue was not the `kill -0` logic but
rather the coordinator v2.0.2 SIGSEGV bug that caused the crash. The monitoring script did
correctly detect the stale PID file and attempted to restart; however, the coordinator
crashed again immediately (same bug), and the second crash happened before the PID file was
written — leaving the old stale PID file in place. The third restart attempt correctly
cleared the stale PID and started the coordinator, which then ran successfully.

The 12-minute downtime was due to the monitoring script's restart delay (30 seconds × 24
retries before the engineer intervened). The SIGSEGV was the root cause; the PID file issue
extended the recovery time.

With systemd, the restart sequence is:
1. Coordinator exits (for any reason)
2. systemd detects exit within milliseconds
3. After `RestartSec=5s`, systemd starts the coordinator again
4. No PID file is involved; systemd tracks the process internally

The recovery time with systemd would have been approximately 5 seconds for the second attempt
(which would have succeeded, as the SIGSEGV was deterministically triggered by a specific job
type that was no longer in the queue after the first crash cleared the queue state).

---

## Section 15: Coordinator Binary and Build Details

### 15.1 Build Environment

The coordinator binary is built from the FinchRender source repository using the Go toolchain
(Go 1.22.0 as of the latest v2.0.4 release). The binary is statically linked with CGO
disabled for portability:

```bash
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build     -ldflags="-w -s -X main.version=2.0.4 -X main.buildDate=$(date -u +%Y-%m-%dT%H:%M:%SZ)"     -o finchrender-coordinator     ./cmd/coordinator/
```

The binary is then verified with `sha256sum` and the hash is recorded in the release notes.

### 15.2 Release Artifact Hashes

| Version | SHA-256 |
|---------|---------|
| v2.0.4 | a7c3f2e8d5b1094c6f3a2e8b5d1074c6f3a2e8b5d1074c6f3a2e8b5d1074c6f |
| v2.0.3 | b8d4g3f9e6c2105d7g4b3f9e6c2105d7g4b3f9e6c2105d7g4b3f9e6c2105d7g |
| v2.0.0 | c9e5h4g0f7d3216e8h5c4g0f7d3216e8h5c4g0f7d3216e8h5c4g0f7d3216e8h |

### 15.3 Shared Library Dependencies

The coordinator binary links against the following shared libraries at runtime:

```
linux-vdso.so.1 (0x00007ffd1c5e5000)
libpthread.so.0 => /lib/x86_64-linux-gnu/libpthread.so.0
libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6
libstdc++.so.6 => /usr/lib/x86_64-linux-gnu/libstdc++.so.6
libgcc_s.so.1 => /lib/x86_64-linux-gnu/libgcc_s.so.1
/lib64/ld-linux-x86-64.so.2
```

All libraries are part of the Debian Bookworm 12 standard distribution. No third-party shared
libraries are required on the coordinator host beyond those provided by the base OS.

### 15.4 Binary Permissions

The coordinator binary is installed with the following permissions:

```
-rwxr-xr-x root:root /usr/local/bin/finchrender-coordinator
```

The binary does NOT have the `setuid` bit set. Privilege management is performed by starting
the binary as root from the systemd unit (or the launcher script) and allowing the binary to
call `setuid`/`setgid`/`capset` internally.

---

## Section 16: OS Requirements and Compatibility

### 16.1 Minimum OS Requirements

| Requirement | Minimum | Current Production |
|-------------|---------|-------------------|
| Linux kernel | 4.11 (capset version 3) | 6.1.0-21 |
| glibc | 2.31 | 2.36 (Debian Bookworm) |
| /proc/sys/kernel/shmmax | accessible | yes |
| tmpfs on /run | required | yes |
| AF_UNIX socket support | required | yes |
| /sys/class/drm | required for GPU | yes |
| /dev/dri/renderD128 | required for GPU | yes |

### 16.2 Kernel Configuration Requirements

The following kernel configuration options must be enabled:

```
CONFIG_UNIX=y                     # UNIX domain sockets
CONFIG_CAPABILITIES=y             # Linux capabilities (POSIX)
CONFIG_SECURITY_CAPABILITIES=y    # Capability bounding sets
CONFIG_DEVPTS_MULTIPLE_INSTANCES=y  # For PrivateTmp (systemd)
CONFIG_CGROUPS=y                  # For systemd resource control
CONFIG_INOTIFY_USER=y             # For cache manager
CONFIG_EPOLL=y                    # Coordinator event loop
```

All of these are enabled in the standard Debian Bookworm kernel configuration.

### 16.3 PAM and NSS Requirements

The coordinator resolves user and group names to numeric IDs via standard `getpwnam` and
`getgrnam` library calls, which in turn use NSS (Name Service Switch) as configured in
`/etc/nsswitch.conf`. On the coordinator host, NSS is configured to use local files only
(`files`): the `finchrender` user and `render` group must exist in `/etc/passwd` and
`/etc/group` respectively.

There is no LDAP, NIS, or other remote directory integration on the coordinator host. User and
group management is performed via local files, and changes are propagated via Ansible playbooks.

### 16.4 systemd Version Requirements

The systemd unit features used in the migration require systemd 245 or later (for
`ProtectProc=`, `MemoryMax=` in cgroup v2 mode). The coordinator host runs:
```
systemd 252 (Debian Bookworm)
```

All unit file directives planned for the coordinator service are supported.

---

## Section 17: Coordinator Internal Architecture

### 17.1 Event Loop Implementation

The coordinator uses a single-threaded event loop based on Linux `epoll`. All file descriptors
(coordinator socket, worker connections, epoll fd) are registered with the epoll instance
(fd 12 in the steady-state lsof output). The event loop calls `epoll_wait` in a tight loop,
with a timeout of -1 (infinite block until an event arrives).

Event dispatch is done via a dispatch table keyed on fd. When `epoll_wait` returns with a
ready fd, the coordinator looks up the handler for that fd in the dispatch table and calls it.
Handlers are lightweight (O(1) in most cases); long-running operations (tile decomposition,
frame assembly) are performed in the `FINCHRENDER_TILE_WORKERS` thread pool.

### 17.2 Thread Pool

The `FINCHRENDER_TILE_WORKERS=8` setting controls the size of the tile-dispatch thread pool.
This is a fixed-size pool of POSIX threads. The coordinator's event loop enqueues tile-dispatch
requests to the thread pool via a work queue (a simple mutex + condition variable based queue).
Each thread in the pool picks up one tile-dispatch request at a time, sends the dispatch
message to the target worker socket, and waits for the acknowledgement before returning to the
idle state.

The use of `CAP_SYS_NICE` allows the coordinator to set the thread pool threads to a lower
priority than the event loop thread, ensuring the event loop remains responsive to new
connections and keepalive messages even when the thread pool is fully utilized.

### 17.3 Memory Management

The coordinator uses a custom arena allocator for job metadata. Each job is allocated a fixed-
size block from the arena, which is pre-allocated at startup (`FINCHRENDER_FRAME_BUFFER_MB`
controls a related but distinct allocation: the frame assembly buffer, which is mmap'd as an
anonymous mapping). The arena allocator was introduced in coordinator v1.3.0 to reduce heap
fragmentation observed under long-running sessions with thousands of small job metadata
allocations.

The frame assembly buffer is a large contiguous memory region used to assemble tiles into
complete frames. It is sized based on `FINCHRENDER_FRAME_BUFFER_MB` (currently 512 MB). The
buffer is divided into `FINCHRENDER_TILE_WORKERS` equal partitions (each 64 MB when tile
workers = 8), and each thread uses one partition exclusively during frame assembly.

### 17.4 IPC Protocol

The coordinator IPC protocol is a simple length-prefixed binary format. Each message begins
with a 4-byte magic number (`0xFCFC0001`), followed by a 2-byte message type, a 4-byte
payload length, and then the payload bytes. The payload format is message-type-specific
and is documented in the `docs/ipc-protocol.md` file in the coordinator source repository.

The magic number was chosen to allow easy identification of coordinator IPC messages in
network captures or core dumps. The `FCFC` prefix is derived from "FinChrender Coordinator".

---

## Section 18: Security Design Rationale

### 18.1 Privilege Drop Timing

The coordinator drops privileges after reading configuration files and looking up user/group
IDs. This means the configuration read window (when the coordinator is still running as root)
is brief (typically 20-50 milliseconds on the coordinator host). The socket creation and bind
happen AFTER the privilege drop, using the `CAP_NET_BIND_SERVICE` capability.

The privilege drop sequence is:
```
1. Read /etc/finchrender/coordinator.yaml  (as root)
2. Read /etc/finchrender/system.toml       (as root)
3. Read /etc/passwd and /etc/group         (as root, for uid/gid lookup)
4. setgid(2001)                            (drop to render group)
5. setuid(2771)                            (drop to finchrender user)
6. capset(...)                             (establish post-drop cap set)
7. prctl(PR_SET_SECUREBITS, ...)           (lock NOROOT bit)
8. Read /proc/sys/kernel/shmmax            (as finchrender)
9. socket() + bind() + listen()            (as finchrender, via CAP_NET_BIND_SERVICE)
```

Steps 8 and 9 onward execute as `finchrender:render` with only `CAP_SYS_NICE` and
`CAP_NET_BIND_SERVICE`. The root window is steps 1-3 only, which are read-only operations
that cannot modify system state.

### 18.2 Socket Security Model

The coordinator socket at `/run/finchrender/coordinator.sock` is created with the following
security properties:
- File owner: `finchrender`
- File group: `render`
- File permissions: `0660` (read-write for owner and group, no access for others)
- Directory owner: `finchrender`
- Directory group: `render`
- Directory permissions: `0755`

Only processes running as `finchrender` user or `render` group members can connect to the
coordinator socket. The gateway and cache manager services both run under the `render` group,
giving them access. Worker nodes connect via the network (the UNIX socket path is only
accessible locally on the coordinator host; workers use a different connection method over the
network — the UNIX socket is for local services only).

### 18.3 Why No Mandatory Access Control

The coordinator does not currently use SELinux, AppArmor, or seccomp profiles. This is a
known gap identified in the 2024 Q1 security audit. The systemd migration will address the
seccomp aspect via `SystemCallFilter` in the service unit. SELinux and AppArmor integration
are planned for a subsequent hardening phase (not in scope for the Q4 2024 migration).

The primary motivation for deferring mandatory access control is the complexity of policy
maintenance. The seccomp approach via systemd's `SystemCallFilter` directive is lower
maintenance than a full SELinux policy or AppArmor profile, and addresses the highest-risk
syscall classes (process creation, module loading, privilege escalation).

---

## Section 19: Testing and Validation History

### 19.1 Coordinator Test Suite

The coordinator has an internal test suite (unit tests in Go) that covers:
- Configuration parsing (YAML and TOML)
- Privilege drop sequence (mocked via test harness)
- Job queue operations (enqueue, dispatch, retry, dequeue)
- Worker registration and heartbeat tracking
- Tile decomposition and frame assembly
- IPC protocol encoding/decoding

The test suite does not include integration tests that exercise the actual socket bind or
privilege drop (these require root; CI runs as an unprivileged user).

### 19.2 Production Smoke Tests

After each coordinator deployment, the following smoke tests are run manually:

1. **Single tile render**: Submit a 1x1-tile render job (a single 256x256 pixel frame).
   Expected: Job completes within 30 seconds, output file appears in frame cache.

2. **Multi-tile render**: Submit a 4K frame render job (135 tiles).
   Expected: Job completes within 15 minutes, all tiles assembled into one frame file.

3. **Worker failover**: While a multi-tile render is in progress, gracefully stop one worker
   node. Expected: In-flight tile is retried on another worker, job completes.

4. **Coordinator reload**: While jobs are in queue, send SIGHUP. Expected: Queue is preserved,
   in-flight jobs complete, new coordinator picks up remaining queue items.

5. **Checkpoint resume**: Kill coordinator (SIGKILL) mid-render. Restart. Expected: In-flight
   tiles are retried, completed tiles are not re-dispatched (checkpoint is read correctly).

### 19.3 Performance Baselines

The following performance baselines were established in Q2 2023 during the capacity planning
exercise:

| Metric | Baseline | Warning Threshold | Critical Threshold |
|--------|---------|-------------------|-------------------|
| Event loop latency (p99) | 1.2 ms | 10 ms | 50 ms |
| Socket accept latency (p99) | 0.3 ms | 5 ms | 20 ms |
| Tile dispatch latency (p99) | 12 ms | 100 ms | 500 ms |
| Frame assembly time (4K, p99) | 780 sec | 1200 sec | 1800 sec |
| Worker heartbeat processing (p99) | 0.1 ms | 1 ms | 5 ms |

These baselines were measured with 8 connected workers and `FINCHRENDER_TILE_WORKERS=8`.
Measurements were taken using the Prometheus histograms, sampled over a 2-hour production
window.

---

## Section 20: Operator Runbooks (Extended)

### 20.1 Changing Environment Variables

Environment variables are read at coordinator startup and are not hot-reloaded (except
`FINCHRENDER_LOG_LEVEL` via SIGHUP). To change an environment variable value:

1. **Edit the environment file**: 
   ```bash
   vim /etc/finchrender/environment
   ```
   (After systemd migration: `vim /etc/finchrender/finchrender.env`)

2. **Verify the edit**: `grep FINCHRENDER /etc/finchrender/environment`

3. **For log-level changes only (hot reload)**:
   ```bash
   kill -HUP $(pgrep -x finchrender-coordinator)
   ```
   Wait 5 seconds, then verify: `grep FINCHRENDER_LOG_LEVEL /proc/$(pgrep -x finchrender-coordinator)/environ | tr '\0' '\n'`

4. **For all other variable changes (requires restart)**:
   - If the change is non-urgent: schedule a maintenance window and follow Section 13.2
   - If the change is urgent: follow Section 13.2 (emergency restart)

5. **Verify the change took effect**: After restart, check the coordinator's active
   environment: `grep FINCHRENDER /proc/$(pgrep -x finchrender-coordinator)/environ | tr '\0' '\n'`

### 20.2 Adding a New Render Node

1. **Provision the new host** (via Ansible playbook `provision-render-node.yml`):
   - Installs OS dependencies
   - Creates the `render` group (gid 2001)
   - Creates the `finchrender` user (uid 2771) as a member of `render`
   - Installs the `finchrender-worker` binary
   - Configures the worker to connect to the coordinator at `10.100.1.10` (the coordinator host)
   - Sets GPU device permissions (`/dev/dri/renderD128`, `render` group, mode 0660)

2. **Start the worker**:
   ```bash
   systemctl enable finchrender-worker && systemctl start finchrender-worker
   ```

3. **Verify registration**: On the coordinator host, check:
   ```bash
   curl -s http://localhost:9090/metrics | grep frc_workers_connected
   ```
   Expected: count increases by 1 within 30 seconds of the worker starting.

4. **Verify worker in dispatch list**:
   ```bash
   finchrender-ctl list-workers
   ```
   Expected: new hostname appears in the list with status `CONNECTED`.

5. **Update the asset inventory** in the ops wiki with the new node's hostname, IP, GPU type,
   and deployment date.

### 20.3 Replacing a Render Node

1. **Drain the old node** (follow Section 13.3: Worker Pool Drain).
2. **Decommission the old node**: Stop the `finchrender-worker` service, shut down the host.
3. **Provision the new node** (follow Section 20.2: Adding a New Render Node).
4. **Verify connectivity and dispatch**: Submit a test render job after the new node registers.
5. **Update asset inventory**: Mark the old node as decommissioned, add the new node.

If replacing due to hardware failure (unplanned):
- Follow Section 13.2 (Emergency Restart) if the coordinator is also affected
- The failed node will be automatically marked offline by the coordinator after the
  `FINCHRENDER_SOCKET_TIMEOUT` window expires
- Proceed with provisioning the replacement node after marking the old one as decommissioned
  in the asset inventory

### 20.4 Coordinator Host Maintenance

For maintenance that requires the coordinator host to be taken offline (kernel upgrade, RAM
replacement, etc.):

1. **Announce maintenance window** in PagerDuty and `#platform-infra` Slack channel.
   Minimum 24-hour advance notice for scheduled maintenance; emergency windows as needed.

2. **Pause job submissions**: Ask the VFX pipeline team to pause new render job submissions
   or use the gateway management API: `finchrender-gw pause-submissions`.

3. **Drain the job queue**: Wait for all in-flight and queued jobs to complete, or checkpoint
   in-progress jobs: `finchrender-ctl checkpoint-all`.

4. **Stop the coordinator**: `systemctl stop finchrender` (or the legacy equivalent).

5. **Notify workers**: Workers will detect the connection loss and enter a reconnect-backoff
   loop. They will not take on new work during this period.

6. **Perform maintenance**.

7. **Start the coordinator**: After the host is back, start the coordinator and verify it
   starts correctly (follow Section 9.2: Post-Upgrade Validation).

8. **Verify worker reconnection**: Workers will reconnect automatically within
   `max(backoff)` = 5 minutes. Verify all 14 workers reconnect.

9. **Resume job submissions**: `finchrender-gw resume-submissions`.

10. **Close the maintenance window** in PagerDuty and notify in Slack.

---

## Section 21: Capacity Planning Extended Analysis

### 21.1 Historical Utilisation Trends

The following table shows monthly peak utilisation for the render farm since its inception:

| Month | Peak Workers | Peak Queue | Peak Throughput | Notes |
|-------|-------------|-----------|-----------------|-------|
| 2022-01 | 4 | 120 | 1,200 rh/day | Initial deployment |
| 2022-04 | 4 | 280 | 1,400 rh/day | Scale-out to 8 workers planned |
| 2022-07 | 8 | 450 | 2,800 rh/day | Q2 scale-out complete |
| 2022-10 | 8 | 620 | 3,100 rh/day | Year-end production crunch |
| 2023-01 | 8 | 380 | 2,900 rh/day | Post-crunch normal |
| 2023-04 | 12 | 580 | 5,200 rh/day | Q1 scale-out to 12 workers |
| 2023-07 | 12 | 720 | 5,800 rh/day | Summer production season |
| 2023-10 | 12 | 950 | 6,100 rh/day | Year-end production crunch |
| 2024-01 | 12 | 680 | 5,900 rh/day | Q1 scale-out to 14 workers planned |
| 2024-04 | 14 | 820 | 7,200 rh/day | Q2 scale-out complete |
| 2024-07 | 14 | 1100 | 7,800 rh/day | Summer season |
| 2024-10 | 14 | 1280 | 8,100 rh/day | Current |

The year-over-year growth rate is consistent at approximately 35%. The Q4 period consistently
shows the highest utilisation due to end-of-year production deadlines.

### 21.2 Bottleneck Analysis

At the current utilisation level (8,000 render-hours/day), the primary bottleneck is GPU
compute on the render nodes, not the coordinator. The coordinator event loop is at 42% of its
benchmark maximum, leaving significant headroom.

If utilisation doubles (to 16,000 render-hours/day, projected for 2026 at the current growth
rate), the coordinator will need to be evaluated for:
- Event loop CPU: May approach 85% of benchmark maximum at 16,000 rh/day; consider switching
  to a multi-threaded event loop model or distributing the coordinator.
- Network bandwidth: The 10 GbE link on the coordinator host may become a bottleneck as frame
  data throughput increases.
- Memory: Frame buffer at 512 MB handles current load; may need increase if 8K rendering
  becomes common.

### 21.3 Storage Growth Projection

| Cache | Current Size | Monthly Growth | 12-Month Projection |
|-------|-------------|---------------|---------------------|
| Tiles | 280 GB | +15 GB/month | 460 GB |
| Frames | 150 GB | +8 GB/month | 246 GB |
| Shaders | 22 GB | +0.5 GB/month | 28 GB |

The coordinator host has 4 TB of NVMe available for cache. At projected growth rates, the
tiles cache will exhaust available space in approximately 240 months (20 years) — the LRU
eviction policy (500 GB ceiling) ensures this never happens. The eviction policy must be kept
active; if it is accidentally disabled (e.g., by stopping the `finchrender-cache` service),
manual intervention would be needed within approximately 30 days at current growth rates.

### 21.4 Render Node Refresh Cycle

Render nodes are expected to be refreshed on a 3-4 year cycle. The Generation 1 nodes
(deployed January 2022) are scheduled for replacement in early 2026. The replacement nodes
will use the latest available GPU (expected: NVIDIA RTX 5090 or equivalent), which should
provide 2-3x the throughput of the current Generation 2 nodes (RTX 4090).

If all Generation 1 nodes are replaced simultaneously with next-generation hardware, total
farm throughput is expected to increase from 28 effective GPU-hours/hour to approximately
48-60 effective GPU-hours/hour. This would push the coordinator event loop from 42% to 70-80%
of benchmark maximum — still within safe operating range but approaching the threshold for
coordinator architecture review.

### 21.5 Systemd Migration Impact on Operations

The systemd migration will improve operational efficiency by:
1. Reducing restart response time from ~30 seconds (monitoring script delay) to ~5 seconds
   (systemd `RestartSec`)
2. Eliminating the stale PID file failure mode (estimated 2-4 incidents per year based on
   historical data)
3. Providing native boot-time ordering (eliminates the `/run/finchrender/` race condition)
4. Adding resource controls (`MemoryMax`, `CPUQuota`) for better resource isolation
5. Improving audit trail via `journald` integration

Based on incident frequency data, the systemd migration is projected to reduce coordinator-
related incident count by approximately 3-4 incidents per year, with an estimated MTTR
reduction from 12 minutes (average for coordinator incidents) to 2 minutes.

### 21.6 Cost Impact of Downtime

The render farm operates on a chargeback model: VFX projects are charged per render-hour.
Each minute of coordinator downtime during production hours (16:00-23:00 UTC) costs
approximately 8 × 1.8 + 6 × 3.1 = 33 effective GPU-hours per hour, or 0.55 GPU-hours per
minute. At the current chargeback rate of $0.75 per GPU-hour, each minute of downtime costs
approximately $0.41 in lost capacity plus staff time for incident response.

For a typical 12-minute incident (historical MTTR), the cost is $5 in lost capacity plus
approximately 2 hours of on-call engineer time (investigation + resolution + incident report).
The systemd migration's projected downtime reduction of 3-4 incidents per year represents
an annual saving of approximately $1,200 in on-call time (at $100/hour) plus $15 in capacity
costs — a straightforward justification for the migration effort.

---

## Section 22: Pre-Migration and Post-Migration Validation

### 22.1 Pre-Migration Validation Checklist

Before cutting over to the systemd unit:

1. **systemd version**: `systemctl --version` ≥ 245
2. **tmpfiles.d unit**: `systemd-tmpfiles --create /etc/tmpfiles.d/finchrender-tmpfiles.conf`
   (dry run, no errors expected)
3. **Service unit syntax**: `systemd-analyze verify /etc/systemd/system/finchrender.service`
   (no errors expected)
4. **Socket unit syntax**: `systemd-analyze verify /etc/systemd/system/finchrender.socket`
   (no errors expected)
5. **Security scan**: `systemd-analyze security finchrender.service` (note current score; target
   is ≤ 5.0 exposure score after all hardening directives)
6. **EnvironmentFile readable**: `test -r /etc/finchrender/finchrender.env && echo OK`
7. **Binary executable**: `test -x /usr/local/bin/finchrender-coordinator && echo OK`
8. **User/group exists**: `id finchrender && getent group render`
9. **Cache directories**: `stat /var/cache/finchrender/{tiles,frames,shaders}` (all owned by
   `finchrender:render`, mode 0750)
10. **GPU device**: `stat /dev/dri/renderD128` (owned `root:render`, mode 0660)

### 22.2 Post-Migration Validation Checklist

After enabling and starting the systemd units:

1. **Socket unit active**: `systemctl is-active finchrender.socket` → `active`
2. **Service unit active**: `systemctl is-active finchrender` → `active`
3. **Process identity**: `systemctl show finchrender --property=MainPID`
   Then: `cat /proc/$MAINPID/status | grep -E 'Uid|Gid|CapEff|CapPrm'`
   Expected Uid: `2771 2771 2771 2771`, Gid: `2001 2001 2001 2001`
   CapEff should decode to `CAP_SYS_NICE|CAP_NET_BIND_SERVICE`
4. **Socket exists**: `stat /run/finchrender/coordinator.sock` (type socket, owner
   `finchrender:render`, mode 0660)
5. **tmpfiles.d applied**: `stat /run/finchrender` (dir, owner `finchrender:render`, mode 0755)
   `stat /var/cache/finchrender/{tiles,frames,shaders}` (dirs, same ownership, mode 0750)
6. **Worker count restored**: `curl -s http://localhost:9090/metrics | grep frc_workers_connected`
   Expected: 14 (all workers reconnected)
7. **Journal logs**: `journalctl -u finchrender -n 50 --no-pager` (no unexpected errors)
8. **Job submission test**: Submit a test job; verify completion.
9. **Restart test**: `systemctl restart finchrender`; verify coordinator restarts cleanly and
   workers reconnect within 60 seconds.
10. **Legacy script disabled**: Verify `rc.local` no longer starts the coordinator
    (`grep finchrender /etc/rc.local` → no match or line is commented out).

*End of extended content*


---

## Section 23: Coordinator Configuration Reference (Complete)

This section provides the complete reference for all configuration options available in the
coordinator's YAML and TOML configuration files. It is intended as a comprehensive reference
for operators and for the systemd migration, which will translate relevant configuration into
the systemd environment file and unit directives.

### 23.1 coordinator.yaml — Complete Field Reference

```yaml
# Service identity and runtime directory
service:
  # Unix username the coordinator drops to after startup
  # Type: string | Default: finchrender | Production: finchrender
  user: finchrender

  # Unix group name for the coordinator runtime identity
  # Type: string | Default: render | Production: render
  group: render

  # Path to the coordinator's UNIX domain socket
  # Type: path | Default: /run/finchrender/coordinator.sock
  # Production: /run/finchrender/coordinator.sock
  socket_path: /run/finchrender/coordinator.sock

  # Path to the PID file written after startup
  # Type: path | Default: /run/finchrender/coordinator.pid
  # Deprecated: Not written when socket activation is used
  pid_file: /run/finchrender/coordinator.pid

  # Maximum number of simultaneously connected worker nodes
  # Type: integer | Default: 8 | Production: 16
  max_workers: 16

  # Minimum number of workers required for job dispatch to be active
  # Type: integer | Default: 2 | Production: 2
  min_workers: 2

# Cache directory configuration
cache:
  # Directory for tile-level render outputs (in-progress frame tiles)
  # Type: path | Default: /var/cache/finchrender/tiles
  tiles_dir: /var/cache/finchrender/tiles

  # Directory for assembled frame buffers
  # Type: path | Default: /var/cache/finchrender/frames
  frames_dir: /var/cache/finchrender/frames

  # Directory for compiled shader programs
  # Type: path | Default: /var/cache/finchrender/shaders
  shaders_dir: /var/cache/finchrender/shaders

  # LRU eviction ceiling for tiles cache (megabytes)
  # Type: integer | Default: 200000 | Production: 500000
  tiles_max_mb: 500000

  # LRU eviction ceiling for frames cache (megabytes)
  # Type: integer | Default: 100000 | Production: 400000
  frames_max_mb: 400000

  # No eviction ceiling for shaders (cleared on restart via tmpfiles.d D directive)
  # Type: integer | Default: 0 (disabled) | Production: 0
  shaders_max_mb: 0

# Logging configuration
logging:
  # Log verbosity level: debug, info, warn, error
  # Type: string | Default: warn | Production: info (FINCHRENDER_LOG_LEVEL overrides)
  level: info

  # Log output file path (stdout if empty)
  # Type: path | Default: "" | Production: /var/log/finchrender/coordinator.log
  file: /var/log/finchrender/coordinator.log

  # Maximum log file size before rotation (megabytes; 0=unlimited)
  # Type: integer | Default: 0 | Production: 200
  max_size_mb: 200

  # Number of rotated log files to retain
  # Type: integer | Default: 5 | Production: 10
  max_backups: 10

# IPC and socket configuration
ipc:
  # Worker connection idle timeout in seconds
  # Type: integer | Default: 60 | Production: 30 (FINCHRENDER_SOCKET_TIMEOUT overrides)
  socket_timeout_sec: 30

  # Socket listen backlog (number of pending connections kernel buffers)
  # Type: integer | Default: 128 | Production: 128
  backlog: 128

  # Management socket path (for finchrender-ctl commands)
  # Type: path | Default: /run/finchrender/coordinator-mgmt.sock
  mgmt_socket_path: /run/finchrender/coordinator-mgmt.sock

# Job queue configuration
queue:
  # Maximum number of jobs in the queue before submissions are rejected
  # Type: integer | Default: 1000 | Production: 1000
  max_depth: 1000

  # Number of priority levels (jobs sorted highest-first within each batch)
  # Type: integer | Default: 3 | Production: 3
  priority_levels: 3

  # How often the dispatcher checks for new work (milliseconds)
  # Type: integer | Default: 100 | Production: 100
  dispatch_interval_ms: 100

# Checkpoint configuration
checkpointing:
  # Enable job checkpoint writing for crash recovery
  # Type: bool | Default: false | Production: true
  enabled: true

  # Write a checkpoint after every N frames complete
  # Type: integer | Default: 10 | Production: 50
  interval_frames: 50

  # Directory for checkpoint files
  # Type: path | Default: /var/lib/finchrender/checkpoints
  checkpoint_dir: /var/lib/finchrender/checkpoints

# Retry configuration
retry:
  # Maximum tile retry attempts before marking tile failed
  # Type: integer | Default: 3 | Production: 3
  max_attempts: 3

  # Base retry backoff in seconds (exponential: base^attempt)
  # Type: integer | Default: 5 | Production: 5
  backoff_base_sec: 5

  # Maximum retry backoff ceiling in seconds
  # Type: integer | Default: 120 | Production: 120
  backoff_max_sec: 120
```

### 23.2 system.toml — Complete Field Reference

```toml
# Tile dispatch worker thread count
# Overridden by FINCHRENDER_TILE_WORKERS environment variable
# Default: 4 | Production: 8
tile_workers = 8

# Frame assembly buffer size in megabytes
# Overridden by FINCHRENDER_FRAME_BUFFER_MB environment variable
# Default: 256 | Production: 512
frame_buffer_mb = 512

# Worker connection idle timeout in seconds
# Overridden by FINCHRENDER_SOCKET_TIMEOUT environment variable
# Default: 60 | Production: 30
socket_timeout = 30

# Log verbosity level: debug, info, warn, error
# Overridden by FINCHRENDER_LOG_LEVEL environment variable
# Default: warn | Production: info
log_level = "info"

[gpu]
# Primary GPU render device path for thumbnail generation
# Type: path | Default: /dev/dri/renderD128
device = "/dev/dri/renderD128"

# Sysfs path for GPU device enumeration at startup
# Type: path | Default: /sys/class/drm
enumerate_via = "/sys/class/drm"

# Maximum GPU memory to use for thumbnail pipeline (megabytes)
# Type: integer | Default: 2048
vram_limit_mb = 2048

[memory]
# Whether to check /proc/sys/kernel/shmmax at startup
# Type: bool | Default: true
shmmax_check = true

# Path to the shmmax kernel parameter (always /proc/sys/kernel/shmmax on Linux)
# Type: path | Default: /proc/sys/kernel/shmmax
shmmax_path = "/proc/sys/kernel/shmmax"

# Minimum acceptable shmmax value (bytes); coordinator exits if below this
# Type: integer | Default: 33554432 (32 MB)
shmmax_minimum = 33554432

[epoll]
# Maximum events per epoll_wait call
# Type: integer | Default: 64
max_events = 64

# epoll_wait timeout in milliseconds (-1 = infinite)
# Type: integer | Default: -1
timeout_ms = -1
```

---

## Section 24: IPC Protocol Detailed Specification

### 24.1 Message Format

Every message on the coordinator UNIX socket uses the following binary format:

```
Offset  Length  Field          Description
0       4       magic          0xFCFC0001 (FinChrender Coordinator, protocol v1)
4       2       msg_type       Message type identifier (see 24.2)
6       4       payload_len    Length of the payload in bytes (0 if no payload)
10      N       payload        Message-specific payload (may be empty)
```

All multi-byte integers are in little-endian byte order. The minimum message size is 10 bytes
(header only, no payload).

### 24.2 Message Types

| Code | Name | Direction | Payload |
|------|------|-----------|---------|
| 0x0001 | REGISTER | Worker→Coordinator | WorkerInfo struct |
| 0x0002 | REGISTER_ACK | Coordinator→Worker | WorkerId (4 bytes) |
| 0x0003 | HEARTBEAT | Worker→Coordinator | Timestamp (8 bytes, Unix nanoseconds) |
| 0x0004 | HEARTBEAT_ACK | Coordinator→Worker | Timestamp (8 bytes) |
| 0x0010 | DISPATCH_TILE | Coordinator→Worker | TileSpec struct |
| 0x0011 | TILE_COMPLETE | Worker→Coordinator | TileResult struct |
| 0x0012 | TILE_FAILED | Worker→Coordinator | TileError struct |
| 0x0020 | SUBMIT_JOB | Gateway→Coordinator | JobSpec struct |
| 0x0021 | JOB_QUEUED | Coordinator→Gateway | JobId (16 bytes, UUID) |
| 0x0022 | JOB_COMPLETE | Coordinator→Gateway | JobResult struct |
| 0x0023 | JOB_FAILED | Coordinator→Gateway | JobError struct |
| 0x0030 | MIGRATING | Coordinator→Worker | Empty payload |
| 0x0031 | DRAIN | Management→Coordinator | WorkerName (string) |
| 0x0032 | DRAIN_ACK | Coordinator→Management | DrainStatus struct |
| 0x00FF | DISCONNECT | Either→Either | Reason (string, optional) |

### 24.3 WorkerInfo Struct

```
Field           Type              Description
hostname        fixed[64]         Worker hostname, null-terminated
version         fixed[16]         Worker binary version string, null-terminated
gpu_model       fixed[64]         GPU model name from /sys/class/drm enumeration
vram_mb         uint32            Available GPU VRAM in megabytes
cpu_cores       uint16            Available CPU cores for tile operations
reserved        uint16            Must be zero
```

Total size: 152 bytes.

### 24.4 TileSpec Struct

```
Field           Type              Description
job_id          fixed[16]         Job UUID (16 bytes, binary)
tile_id         uint32            Tile index within the job
frame_number    uint32            Frame number being rendered
origin_x        uint16            Tile left edge X coordinate (pixels)
origin_y        uint16            Tile top edge Y coordinate (pixels)
width           uint16            Tile width in pixels
height          uint16            Tile height in pixels
samples         uint16            Anti-aliasing sample count
scene_path      fixed[256]        Path to the scene bundle on shared storage
output_path     fixed[256]        Path for the output tile image on shared storage
render_flags    uint32            Bitfield of rendering options (see docs/render-flags.md)
```

Total size: 564 bytes.

---

## Section 25: Coordinator Monitoring Deep-Dive

### 25.1 Prometheus Metric Details

This section provides the complete list of Prometheus metrics exported by the coordinator,
with type, help string, and label details.

**Process Metrics**

`finchrender_coordinator_uptime_seconds` (gauge)  
Help: "Seconds elapsed since the coordinator process started."  
Labels: none  
Notes: Reset to 0 on each coordinator restart. Can be used to detect unexpected restarts.

`finchrender_coordinator_start_timestamp` (gauge)  
Help: "Unix timestamp (seconds) when the coordinator started."  
Labels: none  
Notes: Complements uptime; allows correlating restarts with events on other systems.

`finchrender_coordinator_version_info` (gauge, value always 1)  
Help: "Coordinator version information."  
Labels: `version="2.0.4"`, `go_version="1.22.0"`, `build_date="2024-06-01T12:00:00Z"`  
Notes: Enables version tracking in Grafana dashboards without parsing log files.

`finchrender_coordinator_open_fds` (gauge)  
Help: "Number of open file descriptors in the coordinator process."  
Labels: none  
Notes: Read from `/proc/self/fd` count at each scrape. Expected range: 13-15.

**Event Loop Metrics**

`finchrender_event_loop_iterations_total` (counter)  
Help: "Total number of epoll_wait iterations since start."  
Labels: none

`finchrender_event_loop_events_per_iteration` (histogram)  
Help: "Number of events returned per epoll_wait call."  
Labels: none  
Buckets: 0, 1, 2, 4, 8, 16, 32, 64

`finchrender_event_loop_latency_seconds` (histogram)  
Help: "Time from epoll_wait return to dispatch completion (P50/P95/P99)."  
Labels: none  
Buckets: 0.0001, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0

### 25.2 Grafana Dashboard Structure

The coordinator's operational Grafana dashboard (`finchrender-coordinator` in the Platform
Engineering Grafana org) has the following panel layout:

**Row 1: Overview**
- Coordinator uptime (stat panel)
- Connected workers (stat panel, threshold: 14=green, 10-13=yellow, <10=red)
- Queue depth (stat panel, threshold: <500=green, 500-1000=yellow, >1000=red)
- Current throughput (render-hours/hour) (gauge)

**Row 2: Job Queue**
- Queue depth by priority (stacked time series: high/medium/low)
- Job submission rate (counter, time series)
- Job completion rate (counter, time series)
- Job failure rate by reason (counter, time series)

**Row 3: Workers**
- Worker status heatmap (each worker as a row, time series of 0/1)
- Worker inflight tiles (multi-line time series, one per worker)
- Worker render latency P95 (multi-line time series)
- Worker heartbeat age (multi-line time series, alert at >60s)

**Row 4: Cache**
- Cache size by tier (tiles/frames/shaders) (multi-line time series)
- Cache hit ratio by tier (multi-line time series, alert at <0.5)
- Cache eviction rate (counter, time series)

**Row 5: Process Health**
- Open FD count (time series, alert at >50)
- Memory RSS (time series)
- CPU usage (time series)
- Event loop latency P99 (time series, alert at >10ms)

### 25.3 Log Correlation Guide

When investigating an incident, the following log patterns are useful for correlation:

| Log Pattern | Meaning | Action |
|-------------|---------|--------|
| `[FATAL] shmmax check failed` | shmmax too low for frame buffer | Increase kernel.shmmax |
| `[ERROR] socket bind: ENOENT` | /run/finchrender/ missing | Create dir or check tmpfiles.d |
| `[ERROR] socket bind: EADDRINUSE` | Stale socket file | rm /run/finchrender/coordinator.sock |
| `[WARN] shmmax below recommended` | shmmax low but not fatal | Monitor; may cause OOM |
| `[INFO] worker registered: <name>` | New worker connection | Normal after restart or new node |
| `[INFO] worker disconnected: <name>` | Worker connection closed | Normal or check worker health |
| `[INFO] tile dispatched: job=X tile=Y worker=Z` | Normal dispatch | Verify if rate looks correct |
| `[INFO] tile complete: job=X tile=Y` | Normal completion | Verify if rate looks correct |
| `[WARN] tile retry: job=X tile=Y attempt=N` | Tile failed, retrying | Check worker logs for error |
| `[ERROR] tile failed: job=X tile=Y all retries exhausted` | Job will fail | Check worker logs |
| `[INFO] checkpoint written: job=X frame=Y` | Normal checkpointing | No action needed |
| `[INFO] graceful reload initiated` | SIGHUP received | Normal; reload in progress |
| `[INFO] handover complete, exiting` | Graceful reload done | Verify successor started |
| `[INFO] capset: effective=CAP_SYS_NICE|CAP_NET_BIND_SERVICE` | Normal startup | Confirm cap set is correct |
| `[FATAL] setuid failed` | Can't drop privileges | Check /etc/passwd for finchrender user |
| `[FATAL] setgid failed` | Can't drop group | Check /etc/group for render group |

---

## Section 26: Systemd Unit File Reference (Target State)

This section documents the target state for all systemd unit files that will be created as
part of the Q4 2024 migration. These are design documents, not final implementations — the
actual unit files will be validated and potentially adjusted during the migration testing phase.

### 26.1 finchrender.service (Target)

```ini
[Unit]
Description=FinchRender Render Farm Coordinator
Documentation=https://wiki.internal/finchrender
Requires=finchrender.socket
After=finchrender.socket network.target systemd-tmpfiles-setup.service
After=local-fs.target

[Service]
Type=exec
User=finchrender
Group=render
EnvironmentFile=/etc/finchrender/finchrender.env
ExecStart=/usr/local/bin/finchrender-coordinator     --config /etc/finchrender/coordinator.yaml     --system /etc/finchrender/system.toml
Restart=on-failure
RestartSec=5s
TimeoutStartSec=30s
TimeoutStopSec=30s

# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_UNIX
RestrictNamespaces=yes
LockPersonality=yes
MemoryDenyWriteExecute=no
RestrictRealtime=no
RemoveIPC=yes

# Capability management (post-drop capability set only)
CapabilityBoundingSet=CAP_SYS_NICE CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_SYS_NICE CAP_NET_BIND_SERVICE

# Device access for GPU thumbnail pipeline
DevicePolicy=closed
DeviceAllow=/dev/dri/renderD128 rw

# Path access overrides
ReadOnlyPaths=/proc/sys/kernel/shmmax
ReadWritePaths=/var/cache/finchrender /var/lib/finchrender /var/log/finchrender

# Resource limits
MemoryMax=4G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
```

### 26.2 finchrender.socket (Target)

```ini
[Unit]
Description=FinchRender Coordinator Socket
Documentation=https://wiki.internal/finchrender

[Socket]
ListenStream=/run/finchrender/coordinator.sock
SocketUser=finchrender
SocketGroup=render
SocketMode=0660
Accept=no
Backlog=128
ReusePort=no
DirectoryMode=0755
RuntimeDirectory=finchrender
RuntimeDirectoryMode=0755

[Install]
WantedBy=sockets.target
```

### 26.3 finchrender-tmpfiles.conf (Target)

```
# FinchRender coordinator runtime and cache directories
# Type  Path                                Mode  User         Group   Age
d       /run/finchrender                    0755  finchrender  render  -
D       /var/cache/finchrender/tiles        0750  finchrender  render  -
D       /var/cache/finchrender/frames       0750  finchrender  render  -
D       /var/cache/finchrender/shaders      0750  finchrender  render  -
```

Notes on entry types:
- `d`: Create directory if it does not exist; set permissions on every boot. Does NOT clear contents.
- `D`: Create directory if it does not exist; set permissions; ALSO clear contents on every boot.

The `d` type is used for `/run/finchrender` because the `/run` tmpfs is recreated on every
boot anyway — the directory does not persist, so the contents-clearing semantics of `D` are
redundant. However, for the cache directories (which are on persistent storage), `D` is used
because stale tile and frame data from a previous coordinator invocation should not be served
after a coordinator restart (render jobs are not resumed across reboots; only within the
same coordinator invocation via the checkpoint mechanism).

### 26.4 finchrender.env (Target)

```bash
# FinchRender coordinator environment configuration
# Loaded by finchrender.service via EnvironmentFile=
FINCHRENDER_TILE_WORKERS=8
FINCHRENDER_FRAME_BUFFER_MB=512
FINCHRENDER_SOCKET_TIMEOUT=30
FINCHRENDER_LOG_LEVEL=info
```

This file replaces the role of `/etc/finchrender/environment` in the legacy launcher-script
approach. The `EnvironmentFile=` directive in the service unit causes systemd to read this
file and inject the variables into the coordinator process environment.

The path `/etc/finchrender/finchrender.env` is intentional: the `.env` suffix distinguishes
this file from the legacy `environment` file (which will be kept during the transition period
to support the legacy launcher script on nodes not yet migrated).

---

## Section 27: Failure Mode Analysis

### 27.1 Startup Failure Modes

The following startup failures have been observed in production or identified through analysis:

**FM-1: ENOENT on socket bind**  
Cause: `/run/finchrender/` directory does not exist.  
Symptom: `[ERROR] socket bind: ENOENT /run/finchrender/coordinator.sock`  
Mitigation (legacy): startup script creates directory.  
Mitigation (systemd): `tmpfiles.d d /run/finchrender` + `After=systemd-tmpfiles-setup.service`.  
Historical: INC-2022-0012, INC-2024-0055.

**FM-2: EADDRINUSE on socket bind**  
Cause: Stale socket file from previous unclean shutdown.  
Symptom: `[ERROR] socket bind: EADDRINUSE /run/finchrender/coordinator.sock`  
Mitigation (legacy): `unlink` socket file before bind.  
Mitigation (systemd): Socket is managed by `.socket` unit; no stale socket problem.  
Historical: INC-2023-0008.

**FM-3: Shmmax validation failure**  
Cause: `/proc/sys/kernel/shmmax` is below the minimum threshold (33554432 bytes).  
Symptom: `[FATAL] shmmax check failed: current=16777216 minimum=33554432`  
Mitigation: Set `kernel.shmmax = 67108864` in sysctl.  
Historical: INC-2022-0034.

**FM-4: ENOENT on cache directory open**  
Cause: One or more cache directories under `/var/cache/finchrender/` do not exist.  
Symptom: `[FATAL] cannot open cache dir: /var/cache/finchrender/tiles: ENOENT`  
Mitigation (legacy): Manual `install -d` command.  
Mitigation (systemd): `tmpfiles.d D /var/cache/finchrender/tiles`.  
Historical: INC-2024-0055.

**FM-5: setuid/setgid failure**  
Cause: `finchrender` user (uid 2771) or `render` group (gid 2001) does not exist on the host.  
Symptom: `[FATAL] setgid(2001): Operation not permitted` or similar.  
Mitigation: Ensure user/group exist via Ansible provisioning.  
Historical: No production occurrence; identified in analysis.

**FM-6: GPU enumeration failure**  
Cause: `/sys/class/drm/` exists but contains no device entries (GPU driver not loaded).  
Symptom: `[FATAL] GPU enumeration failed: no render devices found`  
Mitigation: Add `After=udev-settle.service` in systemd unit; retry loop in coordinator.  
Historical: INC-2024-0007.

**FM-7: Capability set failure**  
Cause: The coordinator binary is no longer allowed to call `capset` (rare; would require
a kernel change or security policy change).  
Symptom: `[FATAL] capset failed: Operation not permitted`  
Mitigation: Ensure `AmbientCapabilities` is set correctly in the systemd unit.  
Historical: No production occurrence.

### 27.2 Runtime Failure Modes

**FM-8: FD leak**  
Cause: Bug in the coordinator's epoll event handling (see INC-2024-0033).  
Symptom: `frc_open_fds` gauge increases monotonically; alert fires at >50.  
Mitigation: Upgrade coordinator; monitoring alert provides early warning.  
Historical: INC-2024-0033.

**FM-9: Worker connection storm**  
Cause: Network partition followed by simultaneous reconnection of all workers.  
Symptom: Event loop latency spike; gateway keepalive timeouts; temporary disconnections.  
Mitigation: Exponential backoff in worker reconnect (v1.2.1+).  
Historical: INC-2022-0041.

**FM-10: Tile cache corruption**  
Cause: Coordinator restart during tile assembly leaves partial tile files.  
Symptom: Corrupted render output; cache hit ratio temporarily elevated (hitting corrupt tiles).  
Mitigation: `.partial` file extension mechanism; cache integrity check (v2.0.1+).  
Historical: INC-2023-0037.

**FM-11: OOM kill**  
Cause: Frame buffer allocation for large frames exceeds available RAM.  
Symptom: Coordinator exits with `Killed` message in journal; shmmax warning precedes OOM.  
Mitigation: `FINCHRENDER_FRAME_BUFFER_MB=512` tuned for 4K HDR; `MemoryMax=4G` in systemd unit.  
Historical: INC-2022-0034.

---

## Section 28: Coordinator CLI Tool Reference

The `finchrender-ctl` management tool communicates with the coordinator via the management
socket at `/run/finchrender/coordinator-mgmt.sock`. It is installed alongside the coordinator
binary and must be run as a user with access to the management socket (members of the `render`
group, or root).

### 28.1 Available Commands

`finchrender-ctl status`  
Shows coordinator status: version, uptime, connected workers, queue depth.

`finchrender-ctl list-workers`  
Lists all registered workers with their status, GPU model, and current workload.

`finchrender-ctl list-jobs`  
Lists all queued and in-progress jobs with their status and priority.

`finchrender-ctl drain-worker <hostname>`  
Initiates a graceful drain of the specified worker (stops dispatching new tiles; waits for
in-flight tiles to complete). Returns when the drain is complete.

`finchrender-ctl checkpoint-all`  
Forces an immediate checkpoint write for all in-progress jobs.

`finchrender-ctl reload-config`  
Triggers a SIGHUP-based graceful reload. Equivalent to `kill -HUP`.

`finchrender-ctl pause-dispatch`  
Pauses tile dispatch (jobs remain in queue; no new tiles are sent to workers). Useful for
maintenance operations where you want to allow in-flight tiles to complete but not start
new work.

`finchrender-ctl resume-dispatch`  
Resumes tile dispatch after a pause.

`finchrender-ctl set-log-level <level>`  
Changes the coordinator's log level at runtime (no restart required). Valid levels: debug,
info, warn, error. Equivalent to changing `FINCHRENDER_LOG_LEVEL` and sending SIGHUP.

`finchrender-ctl worker-info <hostname>`  
Shows detailed information about a specific worker: hostname, version, GPU model, VRAM,
CPU cores, current inflight tile count, total tiles completed this session.

`finchrender-ctl job-info <job-id>`  
Shows detailed information about a specific job: submission time, frame range, priority,
current status, completed tile count, failed tile count, estimated completion time.

`finchrender-ctl cancel-job <job-id>`  
Cancels an in-progress or queued job. Workers currently processing tiles from this job are
allowed to complete their current tile; the completed tiles are discarded.

### 28.2 Management Socket Security

The management socket is at `/run/finchrender/coordinator-mgmt.sock` and has permissions:
- Owner: `finchrender`
- Group: `render`
- Mode: `0660`

Only processes running as `finchrender` or in the `render` group can connect to the management
socket. The `finchrender-ctl` tool will fail with a permission error if run as a user not in
the `render` group (unless run as root).

---

## Section 29: Data Retention and Compliance

### 29.1 Log Retention

Coordinator logs are written to `/var/log/finchrender/coordinator.log`. The log rotation
policy is:
- Maximum file size: 200 MB (before rotation)
- Maximum number of rotated files: 10
- Total maximum log disk usage: ~2 GB

Rotated log files are not archived to external storage. Log data is retained for the duration
of the 10-file rotation window (approximately 30-60 days at current log volume).

For compliance purposes, the coordinator logs contain:
- Job submission events (timestamp, submitter identity, job ID)
- Job completion/failure events
- Worker registration and disconnection events
- Privilege drop confirmation (UID/GID transition logged at INFO level)
- Capability set confirmation (capability mask logged at INFO level)

### 29.2 Render Output Retention

Completed frames in `/var/cache/finchrender/frames/` are retained until evicted by the LRU
cache manager (eviction ceiling: 400 GB). The retention period is approximately:
- Normal load (8,000 rh/day): 7-14 days
- Peak load (12,000+ rh/day): 3-7 days

Artists are expected to copy their completed frame sequences to long-term storage (the VFX
pipeline storage system) within 72 hours of job completion. The coordinator does not have
a longer-term retention obligation for render output.

### 29.3 Audit Trail

The coordinator does not maintain a separate audit log. The Prometheus metrics provide
job-level counters (total jobs completed, failed, submitted) that can be used for billing
reconciliation. For detailed per-job audit trails, the job submission gateway maintains its
own audit log.

---

## Section 30: Reference Architecture — Alternate Coordinator Topologies

This section documents two alternative coordinator topologies that were considered during the
Q4 2024 migration planning but are not being implemented at this time. They are documented here
to provide context for future architecture decisions.

### 30.1 Considered: Active-Passive Coordinator HA

**Proposal**: Run two coordinator instances (one active, one standby) with shared state via
a distributed lock (e.g., Consul or etcd). The standby takes over within 30 seconds if the
active coordinator fails.

**Why Not Implemented**: The coordinator's job queue is entirely in-memory; replicating queue
state to a standby would require significant architectural changes to the coordinator. The
current checkpoint mechanism provides crash recovery within a single instance but does not
support live state replication. Given the current MTTR of ~12 minutes (which will be reduced
to ~2 minutes after the systemd migration), the availability improvement from HA does not
justify the implementation complexity. This will be re-evaluated if the MTTR target changes.

### 30.2 Considered: Coordinator Sharding

**Proposal**: Shard the render node pool across multiple coordinator instances (e.g.,
coordinator-a manages workers 1-8, coordinator-b manages workers 9-16). Jobs are assigned
to a shard at submission time by the gateway using a consistent hash of the job ID.

**Why Not Implemented**: Sharding introduces cross-shard job routing complexity and eliminates
the global visibility of cluster state that the coordinator currently provides. At the current
scale (14 workers, 8,000 rh/day), sharding is not needed. The coordinator's event loop
benchmarks indicate headroom for 3-4× growth without architectural changes. This topology
will be considered when coordinator event loop CPU usage exceeds 70% of benchmark maximum.

---

## Section 31: Terminology and Abbreviations

| Term | Definition |
|------|-----------|
| Coordinator | The `finchrender-coordinator` process; central scheduler and dispatcher |
| Worker | A render node running `finchrender-worker`; receives tile dispatch instructions |
| Gateway | The `finchrender-gateway` service; HTTP frontend for job submission |
| Tile | A sub-region of a frame; the unit of work dispatched to a worker |
| Frame | A complete rendered image; assembled from tiles by the coordinator |
| Job | A render request for one or more frames; submitted by an artist via the gateway |
| Cache Manager | The `finchrender-cache` process; manages LRU eviction of cache directories |
| Socket | The UNIX domain socket at `/run/finchrender/coordinator.sock` (unless qualified) |
| Mgmt Socket | The management UNIX socket at `/run/finchrender/coordinator-mgmt.sock` |
| Privilege Drop | The sequence of setgid/setuid/capset calls that transition from root to finchrender |
| Capability Bound | The set of Linux capabilities the coordinator is allowed to retain post-drop |
| Checkpoint | A file recording completed tile states for crash recovery |
| Strace | The system call trace utility; used to instrument the coordinator startup sequence |
| Lsof | The list-open-files utility; used to capture the coordinator's FD profile |
| FD | File descriptor; a kernel-managed handle to an open file, socket, or device |
| tmpfiles.d | systemd's mechanism for creating and managing runtime directories on boot |
| Socket Activation | systemd feature where the coordinator inherits a pre-created socket from systemd |
| MTTR | Mean Time To Recovery; the average time to restore service after an incident |
| rh/day | Render-hours per day; total GPU compute time consumed per day |
| P50/P95/P99 | 50th/95th/99th percentile latency; used in performance metrics |
| Epoll | Linux event notification mechanism; used by the coordinator's event loop |
| LRU | Least Recently Used; eviction policy for cache directories |
| IPC | Inter-Process Communication; specifically the UNIX socket protocol in this document |
| SHM | Shared memory; used by the coordinator's GPU thumbnail pipeline |
| shmmax | Kernel parameter at /proc/sys/kernel/shmmax; maximum shared memory segment size |
| DRM | Direct Rendering Manager; Linux kernel subsystem for GPU access |
| CGO | C Go interface; disabled in the coordinator build for portability |
| NSS | Name Service Switch; Linux mechanism for user/group lookups |
| JM / AR / PK / TL | Initials of platform team members; used in incident reports and change log |

---

*This document is maintained by the Platform Engineering team. Last updated: 2024-10-15.*  
*Questions: #platform-infra Slack channel or INFRA tickets.*


---

## Section 32: Full Strace Session Analysis (Cold Start)

This section provides a detailed walkthrough of the startup-cold.strace file captured on
prod-render-07 on 2024-09-03. The session was captured with:

```bash
strace -f -o /tmp/startup-cold.strace -e trace=all     /usr/local/bin/finchrender-coordinator     --config /etc/finchrender/coordinator.yaml     --system /etc/finchrender/system.toml
```

The trace was reviewed by AR and PK. The following analysis documents every significant syscall
group and its operational meaning.

### 32.1 Phase 1: Dynamic Linker Initialization

The trace begins with the `execve` call that starts the coordinator process. The first argument
to `execve` is the binary path (`/usr/local/bin/finchrender-coordinator`), the second is the
argv array, and the third is the envp array. The envp array in the cold-start trace contains:

```
FINCHRENDER_TILE_WORKERS=8
FINCHRENDER_FRAME_BUFFER_MB=512
FINCHRENDER_SOCKET_TIMEOUT=30
FINCHRENDER_LOG_LEVEL=info
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/var/lib/finchrender
USER=root
LOGNAME=root
```

The `FINCHRENDER_*` environment variables appear first in the envp array because the launcher
script sources the environment file before the PATH and other system variables. The `USER=root`
reflects the pre-drop identity; this variable is not updated after the privilege drop (Unix
environment variables are inherited and not automatically updated by `setuid`).

Following `execve`, the dynamic linker initialization sequence produces approximately 80 syscalls:
- `arch_prctl(ARCH_SET_FS, ...)`: sets the thread-local storage base address
- Multiple `openat/read/close` sequences for library files: `/etc/ld.so.cache`,
  `/lib/x86_64-linux-gnu/libpthread.so.0`, `/lib/x86_64-linux-gnu/libc.so.6`,
  `/usr/lib/x86_64-linux-gnu/libstdc++.so.6`, `/lib/x86_64-linux-gnu/libgcc_s.so.1`
- Multiple `mmap/mprotect` calls to map each library into the address space
- `set_tid_address`, `set_robust_list`, `rseq` for thread-local housekeeping
- `prlimit64(0, RLIMIT_STACK, NULL, ...)` to query the stack size limit

None of these calls are coordinator-specific; they are standard dynamic linker behavior.

### 32.2 Phase 2: Configuration Read

After the dynamic linker completes, the coordinator's `main()` function runs. The first
operations are configuration reads:

```
openat(AT_FDCWD, "/etc/finchrender/coordinator.yaml", O_RDONLY|O_CLOEXEC) = 3
read(3, "service:
  user: finchrender
  g"..., 4096) = 421
close(3) = 0
openat(AT_FDCWD, "/etc/finchrender/system.toml", O_RDONLY|O_CLOEXEC) = 3
read(3, "[system]
tile_workers = 8
frame_"..., 4096) = 234
close(3) = 0
```

Both configuration files are opened, read completely in a single `read` call, and closed
immediately. The `O_CLOEXEC` flag ensures these file descriptors are automatically closed
if the coordinator ever forks and exec's a child process.

The `421` byte read for `coordinator.yaml` corresponds to the full file size (the file
contains approximately 420 bytes of YAML). Similarly, `234` bytes for `system.toml`.

### 32.3 Phase 3: User and Group Lookup

The coordinator resolves the username `finchrender` and group name `render` to their numeric
IDs by reading `/etc/passwd` and `/etc/group`:

```
openat(AT_FDCWD, "/etc/passwd", O_RDONLY|O_CLOEXEC) = 3
fstat(3, {st_mode=S_IFREG|0644, st_size=1987, ...}) = 0
lseek(3, 0, SEEK_SET) = 0
read(3, "root:x:0:0:root:/root:/bin/bash
"..., 4096) = 1987
close(3) = 0
openat(AT_FDCWD, "/etc/group", O_RDONLY|O_CLOEXEC) = 3
fstat(3, {st_mode=S_IFREG|0644, st_size=867, ...}) = 0
read(3, "root:x:0:
daemon:x:1:
...
render"..., 4096) = 867
close(3) = 0
```

The `fstat` call checks file size before reading, allowing the `read` buffer to be sized
correctly. The `lseek` before the `passwd` read is a `getpwnam` implementation detail
(re-seeking to start for a fresh scan). Both files are read completely in single calls.

The `1987` bytes of `/etc/passwd` contains all local users including `finchrender`. Scanning
reveals the entry: `finchrender:x:2771:2001::/var/lib/finchrender:/usr/sbin/nologin`.
The `867` bytes of `/etc/group` contains all local groups including `render:x:2001:finchrender`.

### 32.4 Phase 4: Capability Queries (Pre-Drop)

Before dropping privileges, the coordinator queries the current capability set:

```
capget({version=_LINUX_CAPABILITY_VERSION_3, pid=0}, NULL) = 0
capget({version=_LINUX_CAPABILITY_VERSION_3, pid=0}, {effective=CAP_CHOWN|CAP_DAC_OVERRIDE|CAP_SETGID|CAP_SETUID|CAP_SYS_NICE|CAP_NET_BIND_SERVICE, permitted=CAP_CHOWN|CAP_DAC_OVERRIDE|CAP_SETGID|CAP_SETUID|CAP_SYS_NICE|CAP_NET_BIND_SERVICE, inheritable=0x0}) = 0
```

The first `capget` call (with NULL second argument) retrieves the capability API version.
The second `capget` call retrieves the actual capability bits. The result shows the full
root capability set: `CAP_CHOWN` (0), `CAP_DAC_OVERRIDE` (1), `CAP_SETGID` (6),
`CAP_SETUID` (7), `CAP_SYS_NICE` (23), `CAP_NET_BIND_SERVICE` (10).

**Important**: These pre-drop capabilities are NOT the capabilities the coordinator retains.
They are the capabilities present while the coordinator is still running as root. The
subsequent `capset` call after `setuid`/`setgid` establishes the final capability set.

The pre-drop `capget` result is used by the coordinator to log what capabilities it is
surrendering, for audit trail purposes.

### 32.5 Phase 5: Privilege Drop Sequence

```
setgid(2001) = 0
setuid(2771) = 0
capset({version=_LINUX_CAPABILITY_VERSION_3, pid=0}, {effective=CAP_SYS_NICE|CAP_NET_BIND_SERVICE, permitted=CAP_SYS_NICE|CAP_NET_BIND_SERVICE, inheritable=0x0}) = 0
prctl(PR_SET_SECUREBITS, SECBIT_NOROOT|SECBIT_NOROOT_LOCKED, 0, 0, 0) = 0
prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, CAP_SYS_NICE, 0, 0) = 0
prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, CAP_NET_BIND_SERVICE, 0, 0) = 0
```

This sequence is the most security-critical part of the startup. Line by line:

1. `setgid(2001)`: Drop the supplementary groups and set the real, effective, and saved group
   IDs to 2001 (the `render` group). After this call, the process's group identity is `render`.

2. `setuid(2771)`: Drop the real, effective, and saved user IDs to 2771 (the `finchrender`
   user). After this call, the process is no longer root. Note: `setuid` is called AFTER
   `setgid` because `setuid` on a non-root process cannot change group identity.

3. `capset(...)`: This is the definitive capability-setting call. The argument sets:
   - `effective = CAP_SYS_NICE | CAP_NET_BIND_SERVICE` (capabilities usable by the process)
   - `permitted = CAP_SYS_NICE | CAP_NET_BIND_SERVICE` (capabilities the process may raise)
   - `inheritable = 0x0` (capabilities inherited by exec'd subprocesses: none)
   
   This call establishes the final, post-drop capability mask. All other capabilities
   (CAP_CHOWN, CAP_DAC_OVERRIDE, CAP_SETGID, CAP_SETUID, etc.) are dropped here.

4. `prctl(PR_SET_SECUREBITS, SECBIT_NOROOT|SECBIT_NOROOT_LOCKED, ...)`: Locks the `NOROOT`
   secure bit. This prevents the `finchrender` user from gaining capabilities by executing
   setuid root binaries. The `LOCKED` flag prevents the secure bit from being cleared.

5. Two `prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, ...)` calls: Raise `CAP_SYS_NICE` and
   `CAP_NET_BIND_SERVICE` into the ambient capability set. This is needed for socket activation
   compatibility: when the coordinator is started by systemd with socket activation, the
   coordinator process must be able to call `bind()` on the inherited socket; the ambient
   capability set ensures the capability is available even in the fd-inheritance code path.

### 32.6 Phase 6: Shmmax Check and Socket Operations

```
openat(AT_FDCWD, "/proc/sys/kernel/shmmax", O_RDONLY) = 3
read(3, "33554432
", 64) = 9
close(3) = 0
socket(AF_UNIX, SOCK_STREAM|SOCK_CLOEXEC, 0) = 5
bind(5, {sa_family=AF_UNIX, sun_path="/run/finchrender/coordinator.sock"}, 48) = 0
listen(5, 128) = 0
```

Note: the shmmax read shows `33554432` (32 MB). This is below the `shmmax_minimum = 33554432`
(32 MB, equal, not below). The coordinator logged an INFO message confirming the value meets
the minimum. The `shmmax_check = true` setting in `system.toml` enables this check; if
shmmax were below 33554432, the coordinator would exit with code 1 after logging the error.

After the shmmax check, the coordinator creates and binds the UNIX socket:
- `socket(AF_UNIX, SOCK_STREAM|SOCK_CLOEXEC, 0) = 5`: Creates a UNIX stream socket, file
  descriptor 5. The `SOCK_CLOEXEC` flag is set to prevent the socket from leaking to child
  processes via `fork/exec`.
- `bind(5, {AF_UNIX, "/run/finchrender/coordinator.sock"}, 48) = 0`: Binds the socket to
  the filesystem path. The `48` is the struct size of `sockaddr_un` with the 34-char path.
  Requires that `/run/finchrender/` directory exists and is writable by `finchrender`.
- `listen(5, 128) = 0`: Sets the listen backlog to 128.

### 32.7 Phase 7: GPU and Cache Access

```
openat(AT_FDCWD, "/dev/dri/renderD128", O_RDWR|O_CLOEXEC) = 6
close(6) = 0
openat(AT_FDCWD, "/sys/class/drm", O_RDONLY|O_DIRECTORY|O_CLOEXEC) = 6
getdents64(6, /* 8 entries */, 32768) = 232
close(6) = 0
openat(AT_FDCWD, "/var/cache/finchrender/tiles", O_RDONLY|O_DIRECTORY|O_CLOEXEC) = 6
openat(AT_FDCWD, "/var/cache/finchrender/frames", O_RDONLY|O_DIRECTORY|O_CLOEXEC) = 7
openat(AT_FDCWD, "/var/cache/finchrender/shaders", O_RDONLY|O_DIRECTORY|O_CLOEXEC) = 8
```

The GPU device (`/dev/dri/renderD128`) is opened read-write during startup for capability
checking, then immediately closed (fd 6 is reused). The actual GPU handle for the thumbnail
pipeline is opened later when a thumbnail job arrives.

The sysfs DRM directory is opened for enumeration: `getdents64` reads 8 directory entries
(the 8 DRM devices/connectors present in `/sys/class/drm/`). After enumeration, the directory
handle is closed.

The three cache directories are opened read-only (`O_RDONLY|O_DIRECTORY|O_CLOEXEC`) and their
file descriptors are held open for the coordinator's lifetime. These directory file descriptors
(fds 6, 7, 8) are used for `openat()` calls within the cache management code — opening a file
descriptor to a directory allows using `openat(dirfd, filename, ...)` without needing to
re-resolve the full path on every cache access.

---

## Section 33: Full lsof Session Analysis (Steady State)

### 33.1 lsof Capture Methodology

The steady-state lsof capture was taken after the coordinator had been running for
approximately 4 hours with a normal production load. The capture command was:

```bash
lsof -p $(pgrep -x finchrender-coordinator) -n -P
```

The `-n` flag suppresses hostname resolution (no DNS lookups), and `-P` suppresses port name
resolution. This produces numeric output for all network addresses.

### 33.2 lsof Output Interpretation

The standard lsof output columns for the coordinator process:

| Column | Description | Example |
|--------|-------------|---------|
| COMMAND | Process name (truncated to 15 chars) | `finchren-c` |
| PID | Process ID | `1234` |
| USER | Effective username | `finchrender` |
| FD | File descriptor number and access mode | `5u` = fd 5, read-write |
| TYPE | File type | `REG`, `DIR`, `unix`, `CHR`, etc. |
| DEVICE | Device number (major, minor) | `8,1` |
| SIZE/OFF | File size or offset | `4096` |
| NODE | Inode number (for regular files) or socket id | `678` |
| NAME | File path or socket description | `/var/cache/finchrender/tiles` |

### 33.3 FD Access Mode Codes

| Mode | Meaning |
|------|---------|
| `r` | Read |
| `w` | Write |
| `u` | Read and write |
| (none) | Unknown |

The FD column format is: digits (fd number) followed by the access mode character followed
optionally by `W` (write lock), `R` (read lock), or `N` (no lock).

For example: `5u` = file descriptor 5, opened for both read and write.

### 33.4 FD Type Classification for Exclusion

When counting the coordinator's file descriptors for the ≤15 bound, the following lsof
TYPE/FD combinations are EXCLUDED (they are not kernel fd table entries):

| FD value | Description | Excluded because |
|----------|-------------|-----------------|
| `cwd` | Current working directory | Not a kernel fd; represents the process's cwd |
| `rtd` | Root directory | Not a kernel fd; represents the process's root |
| `txt` | Program text (executable) | Not a kernel fd; the executable mapping |
| `mem` | Memory-mapped file | Not a kernel fd; a library mapping |
| `DEL` | Deleted memory-mapped file | Not a kernel fd; a deleted mapping |

All other entries (including entries with `a_inode` type for epoll/eventfd/signalfd) ARE
counted as kernel file descriptors.

### 33.5 Steady-State FD Count Verification

The steady-state lsof capture (from `/app/traces/steady-state.lsof`) lists:

Excluded (cwd, rtd, txt, mem×3): 6 rows  
Included fds: 0r, 1w, 2w, 3r, 4r, 5u, 6r, 7r, 8r, 9r, 10rw, 11r, 12u = 13 fds

Total steady-state FD count: **13**

The under-load lsof capture (`/app/traces/under-load.lsof`) adds two worker connection
sockets (fds 13u and 14u) for a total of:

Total under-load FD count: **15**

This matches the documented bound of "no more than 15 open file descriptors during normal
operation." Both captures are available in `/app/traces/` for verification.

---

## Section 34: Migration Risk Register

### 34.1 Risk Assessment

The following risks have been identified for the Q4 2024 systemd migration:

**RISK-01: Coordinator Binary Incompatible with systemd Socket Activation**  
Likelihood: Low  
Impact: High (migration blocked)  
Description: The coordinator v2.0.4 binary may not correctly detect the `LISTEN_FDS`
environment variable and inherit the socket from systemd, instead always attempting to
create a new socket.  
Mitigation: Test socket activation in a staging environment before production rollout.
The coordinator binary was reviewed and does implement `sd_listen_fds(3)` from libsystemd.  
Status: Mitigation applied (staging test planned for 2024-11-01).

**RISK-02: tmpfiles.d D Directive Clears Active Cache Data**  
Likelihood: Medium  
Impact: Medium (cache warm-up delay; not production-blocking)  
Description: The `D` directive for cache directories clears contents on every boot. If a
reboot occurs during production hours, the tile and frame caches will be empty, reducing
cache hit rates and increasing render times for the first few hours post-reboot.  
Mitigation: Reboots of the coordinator host should be scheduled during off-peak hours
(00:00-08:00 UTC). Cache warm-up time is approximately 30-60 minutes.  
Status: Accepted risk with procedure control.

**RISK-03: CapabilityBoundingSet Blocks Unexpected Coordinator Requirement**  
Likelihood: Low  
Impact: High (coordinator fails to start or perform required operations)  
Description: The `CapabilityBoundingSet=CAP_SYS_NICE CAP_NET_BIND_SERVICE` directive will
cause the coordinator to fail if any code path requires a capability not in this set.  
Mitigation: The strace analysis confirms the coordinator's `capset` call requests exactly
these two capabilities. Additional review of the coordinator source code (Go) confirmed no
other capability use.  
Status: Mitigation applied.

**RISK-04: DeviceAllow Policy Blocks GPU Access Under Load**  
Likelihood: Low  
Impact: Medium (thumbnail generation fails; thumbnails fall back to software rendering)  
Description: The `DevicePolicy=closed` + `DeviceAllow=/dev/dri/renderD128 rw` combination
may not correctly allow GPU access if the device node number changes (e.g., after a kernel
upgrade). Device node numbers are dynamic.  
Mitigation: Test GPU access after systemd unit deployment. Use `DeviceAllow=/dev/dri/ rw`
as a broader allowance if specific node number causes issues (broader scope acceptable given
the coordinator runs as `finchrender:render` with restricted filesystem access).  
Status: Open; to be addressed during staging testing.

**RISK-05: ProtectSystem=strict Blocks Config File Writes**  
Likelihood: Low  
Impact: Low (coordinator does not normally write to /etc/)  
Description: `ProtectSystem=strict` makes `/usr`, `/boot`, `/efi`, and `/etc` read-only.
If any coordinator code path attempts to write to `/etc/finchrender/`, it will fail.  
Mitigation: Review of coordinator source code confirms no writes to `/etc/`. Config files
are read-only from the coordinator's perspective.  
Status: Mitigation applied.

### 34.2 Migration Rollback Plan

If the systemd migration encounters a blocking issue in production:

1. **Disable systemd units**: `systemctl disable --now finchrender.service finchrender.socket`
2. **Restore legacy startup**: Uncomment the `rc.local` entry for the coordinator launcher
3. **Restart coordinator via legacy launcher**: `/usr/local/bin/finchrender-launcher`
4. **Verify operation**: Check worker reconnection and job processing resume
5. **File a post-mortem**: Document the blocking issue and file a follow-up ticket

The rollback is designed to complete within 5 minutes. The systemd units and the legacy
launcher can coexist on the host; they are mutually exclusive by design (only one coordinator
should be running at a time).

---

## Section 35: Coordinator Source Code Structure Reference

The coordinator source code lives in the FinchRender monorepo under `services/coordinator/`.
This section documents the source code structure for the benefit of engineers working on the
migration who may need to understand how specific behaviors are implemented.

### 35.1 Source Tree

```
services/coordinator/
  cmd/
    coordinator/
      main.go          # Entry point; flag parsing, startup sequence
  internal/
    config/
      yaml.go          # coordinator.yaml parser
      toml.go          # system.toml parser
    privilege/
      drop.go          # setgid/setuid/capset sequence
      caps.go          # capability set management
      shmmax.go        # /proc/sys/kernel/shmmax check
    socket/
      server.go        # UNIX socket create/bind/listen
      handler.go       # Connection accept loop
      protocol.go      # IPC message encode/decode
    worker/
      registry.go      # Worker registration and heartbeat tracking
      dispatch.go      # Tile dispatch to workers
      pool.go          # Thread pool for dispatch operations
    job/
      queue.go         # Priority queue implementation
      scheduler.go     # Job decomposition and tile scheduling
      checkpoint.go    # Checkpoint read/write
    cache/
      manager.go       # Interface to cache manager via mgmt socket
      directory.go     # Cache directory open/stat operations
    gpu/
      enum.go          # /sys/class/drm enumeration
      device.go        # /dev/dri/renderD128 open/close
      thumbnail.go     # GPU thumbnail pipeline
    metrics/
      prometheus.go    # Prometheus exporter HTTP handler
    log/
      logger.go        # Structured logging with level support
  go.mod
  go.sum
```

### 35.2 Privilege Drop Implementation

The privilege drop is implemented in `internal/privilege/drop.go`. The key function is
`DropPrivileges(cfg *config.ServiceConfig)`:

```go
func DropPrivileges(cfg *config.ServiceConfig) error {
    // Resolve uid/gid by name lookup
    uid, gid, err := resolveIdentity(cfg.User, cfg.Group)
    if err != nil {
        return fmt.Errorf("identity lookup: %w", err)
    }

    // Drop group first (must be done while still root)
    if err := syscall.Setgid(gid); err != nil {
        return fmt.Errorf("setgid(%d): %w", gid, err)
    }

    // Drop user
    if err := syscall.Setuid(uid); err != nil {
        return fmt.Errorf("setuid(%d): %w", uid, err)
    }

    // Set post-drop capability mask
    if err := caps.SetPostDropCapabilities(); err != nil {
        return fmt.Errorf("capset: %w", err)
    }

    // Lock NOROOT secure bit
    if err := prctl(PR_SET_SECUREBITS, SECBIT_NOROOT|SECBIT_NOROOT_LOCKED); err != nil {
        return fmt.Errorf("prctl(PR_SET_SECUREBITS): %w", err)
    }

    // Raise ambient capabilities
    for _, cap := range []uintptr{CAP_SYS_NICE, CAP_NET_BIND_SERVICE} {
        if err := prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, cap); err != nil {
            return fmt.Errorf("prctl(PR_CAP_AMBIENT_RAISE, %d): %w", cap, err)
        }
    }

    return nil
}
```

The `caps.SetPostDropCapabilities()` function calls `capset` with the approved capability
mask: `effective = CAP_SYS_NICE | CAP_NET_BIND_SERVICE`, same for `permitted`,
`inheritable = 0`.

### 35.3 Shmmax Check Implementation

The shmmax check is implemented in `internal/privilege/shmmax.go`. It is called after the
privilege drop (the `/proc/sys/kernel/shmmax` pseudofile is readable by all users):

```go
func CheckShmmax(cfg *config.MemoryConfig) error {
    f, err := os.Open(cfg.ShmmaxPath)   // Opens /proc/sys/kernel/shmmax
    if err != nil {
        return fmt.Errorf("open %s: %w", cfg.ShmmaxPath, err)
    }
    // Note: f is NOT closed here; the fd is stored in the ShmmaxWatcher
    // for periodic re-reads during the coordinator's lifetime.
    w := &ShmmaxWatcher{f: f, minimum: cfg.ShmmaxMinimum}
    val, err := w.Read()
    if err != nil {
        return fmt.Errorf("read %s: %w", cfg.ShmmaxPath, err)
    }
    if val < cfg.ShmmaxMinimum {
        return fmt.Errorf("shmmax %d < minimum %d", val, cfg.ShmmaxMinimum)
    }
    log.Infof("shmmax check passed: current=%d minimum=%d", val, cfg.ShmmaxMinimum)
    return nil
}
```

The important detail here is "Note: f is NOT closed here". The file handle is stored in a
`ShmmaxWatcher` struct and remains open for the lifetime of the process. This is the
mechanism that causes `/proc/sys/kernel/shmmax` to appear in the lsof steady-state output
(fd 9 in the capture).

---

## Section 36: Long-Term Roadmap Items

The following items have been discussed but are not in scope for the current Q4 2024 migration.
They are documented here to capture the context for future decisions.

### 36.1 Coordinator High Availability

As documented in Section 30.1, active-passive HA for the coordinator was considered and
rejected for the current scope. The systemd migration is a prerequisite for any future HA
implementation because:

1. `systemd` provides the health-check plumbing (`HealthCheckSec`, `WatchdogSec`) that would
   be needed to trigger failover at the system level.
2. With socket activation, the socket lifecycle is decoupled from the coordinator process,
   making it easier to implement socket handover to a standby process.
3. The `Restart=on-failure` policy in the systemd unit provides a basic form of self-healing
   that covers the most common failure modes without requiring a full HA architecture.

If HA becomes a requirement (likely at 99.9% → 99.99% SLA escalation), the implementation
path would be:
1. Add `sd_notify(3)` support to the coordinator (for `Type=notify`)
2. Add external health monitoring via the Prometheus metrics
3. Evaluate Keepalived or Pacemaker for IP failover
4. Or: implement coordinator-level active-passive with shared state in etcd/Consul

### 36.2 Container Migration

Several team members have raised the possibility of containerising the coordinator in Docker
or containerd. This would provide additional isolation and simplify deployments. The primary
obstacles are:

1. The coordinator requires access to `/dev/dri/renderD128` (GPU device) inside the container.
   This is achievable with Docker's `--device /dev/dri/renderD128` flag, but requires the
   device to be available on the host.
2. The UNIX socket at `/run/finchrender/coordinator.sock` needs to be accessible to the
   gateway and cache manager services. In a container deployment, these would also need to
   be containerised or the socket would need to be volume-mounted.
3. The coordinator's privilege drop model (starting as root and dropping to uid 2771) is
   compatible with containers, but the `CAP_SYS_NICE` and `CAP_NET_BIND_SERVICE` capabilities
   would need to be explicitly granted to the container (`--cap-add SYS_NICE NET_BIND_SERVICE`).

A containerised deployment is on the 2025 technology roadmap but is not in the current
migration scope.

### 36.3 seccomp Profile

The 2024 Q1 security audit recommended adding a seccomp profile to restrict the syscalls
the coordinator is allowed to make. The systemd unit's `SystemCallFilter` directive is the
mechanism for this.

The strace session provides the complete list of syscalls made by the coordinator in a cold
start and steady-state operation. A comprehensive `SystemCallFilter` would whitelist:
- `epoll_*`, `socket`, `bind`, `listen`, `accept4`, `connect`
- `open`, `openat`, `read`, `write`, `close`, `fstat`, `lseek`
- `mmap`, `mprotect`, `munmap`
- `setuid`, `setgid`, `capget`, `capset`
- `prctl` (with argument filtering if supported)
- `rt_sigaction`, `rt_sigreturn`
- `clone`, `wait4` (for the graceful reload fork)
- `exit_group`

The systemd `@system-service` predefined filter is a reasonable starting point that would
need to be supplemented with the coordinator-specific syscalls listed above. Implementing
the filter is estimated at 2-4 hours of work and will be done as a follow-up to the initial
systemd migration.

---

*End of Supplementary Sections*


---

## Section 37: Migration Implementation Guide for TypeScript Tooling

The systemd migration will be implemented via TypeScript tooling that:
1. Reads the strace and lsof captures to extract runtime contracts
2. Generates the target systemd unit files based on those contracts
3. Validates the generated files against the dossier requirements

This section provides the specification for the output formats that the tooling must produce.

### 37.1 contracts.json Output Format

The `contracts.json` file captures the runtime identity and access requirements extracted
from the strace session, lsof session, and dossier review. It must conform to this schema:

```json
{
  "user": "finchrender",
  "group": "render",
  "sockets": [
    "/run/finchrender/coordinator.sock"
  ],
  "capabilities": [
    "CAP_SYS_NICE",
    "CAP_NET_BIND_SERVICE"
  ],
  "cache_dirs": [
    "/var/cache/finchrender/tiles",
    "/var/cache/finchrender/frames",
    "/var/cache/finchrender/shaders"
  ],
  "env_vars": {
    "FINCHRENDER_TILE_WORKERS": "8",
    "FINCHRENDER_FRAME_BUFFER_MB": "512",
    "FINCHRENDER_SOCKET_TIMEOUT": "30",
    "FINCHRENDER_LOG_LEVEL": "info"
  },
  "policy_exceptions": [
    {
      "path": "/proc/sys/kernel/shmmax",
      "access": "read",
      "rationale": "shmmax pre-flight check at startup and periodic re-read"
    },
    {
      "path": "/dev/dri/renderD128",
      "access": "rw",
      "rationale": "GPU render device for thumbnail generation and scene pre-processing"
    },
    {
      "path": "/sys/class/drm",
      "access": "read",
      "rationale": "GPU device enumeration at startup"
    }
  ],
  "fd_count_observed": 15
}
```

Field definitions:
- `user` (string): The username the coordinator drops to, extracted from strace `setuid` arg
  resolved via `/etc/passwd` (or from the coordinator.yaml `service.user` field as corroboration)
- `group` (string): The group name from strace `setgid` arg resolved via `/etc/group`
- `sockets` (string[]): UNIX socket paths from strace `bind(AF_UNIX, ...)` calls
- `capabilities` (string[]): Capability names from the FINAL `capset` call's effective set
- `cache_dirs` (string[]): Directory paths from strace `openat(..., O_DIRECTORY, ...)` calls
  that are held open (appear in lsof steady-state with `DIR` type)
- `env_vars` (object): Key-value pairs from the `execve` envp array filtered to `FINCHRENDER_*`
- `policy_exceptions` (array): Access requirements documented in ops-dossier.md that are not
  directly observable in the strace/lsof (because they are mentioned in prose, not as syscalls)
- `fd_count_observed` (number): Maximum FD count observed across all lsof captures

### 37.2 Expected Systemd Output Files

The generate step must produce exactly four files under `/app/output/`:

**finchrender.service** — systemd service unit for the coordinator.
Must contain at minimum:
- `[Unit]` section with `Description=` and `After=` directives
- `[Service]` section with `Type=`, `User=finchrender`, `Group=render`
- `EnvironmentFile=` pointing to the env file
- `ExecStart=` with the coordinator binary path
- `NoNewPrivileges=yes` and `PrivateTmp=yes`
- `CapabilityBoundingSet=CAP_SYS_NICE CAP_NET_BIND_SERVICE`
- `AmbientCapabilities=CAP_SYS_NICE CAP_NET_BIND_SERVICE`
- `DeviceAllow=/dev/dri/renderD128 rw`

**finchrender.socket** — systemd socket unit.
Must contain:
- `[Socket]` section with `ListenStream=/run/finchrender/coordinator.sock`
- Socket ownership directives

**finchrender-tmpfiles.conf** — tmpfiles.d configuration.
Must contain:
- `d /run/finchrender ...` line (runtime socket directory)
- `D /var/cache/finchrender/tiles ...` line
- `D /var/cache/finchrender/frames ...` line
- `D /var/cache/finchrender/shaders ...` line

**finchrender.env** — environment file.
Must contain all four `FINCHRENDER_*` variables with production values.

### 37.3 validation-report.json Output Format

The `validation-report.json` file reports the results of cross-checking the generated unit
files against the contracts and dossier requirements:

```json
{
  "passed": true,
  "policy_exceptions_covered": [
    {
      "path": "/proc/sys/kernel/shmmax",
      "directive": "ReadOnlyPaths=/proc/sys/kernel/shmmax"
    },
    {
      "path": "/dev/dri/renderD128",
      "directive": "DeviceAllow=/dev/dri/renderD128 rw"
    },
    {
      "path": "/sys/class/drm",
      "directive": "ReadOnlyPaths=/sys/class/drm"
    }
  ],
  "fd_count_valid": true,
  "tmpfiles_complete": true,
  "issues": []
}
```

Field definitions:
- `passed` (boolean): true if all checks pass; false if any issue is found
- `policy_exceptions_covered` (array): for each policy exception in contracts.json, the
  corresponding directive in the generated finchrender.service that provides access
- `fd_count_valid` (boolean): true if the observed fd count from under-load.lsof is ≤ 15
- `tmpfiles_complete` (boolean): true if finchrender-tmpfiles.conf contains entries for all
  cache_dirs in contracts.json plus the /run/finchrender socket directory
- `issues` (string[]): list of validation failures (empty if passed=true)

---

## Section 38: Cross-Reference Index

This section provides a quick-reference index mapping key values to the locations in this
dossier where they are established or discussed.

### 38.1 User and Group Identity

| Value | Type | Primary Source | Sections |
|-------|------|---------------|---------|
| `finchrender` | username | strace setuid(2771) + /etc/passwd | §4.1, §4.2, §32.5 |
| 2771 | uid | strace setuid call | §32.5 |
| `render` | group name | strace setgid(2001) + /etc/group | §4.1, §4.2, §32.5 |
| 2001 | gid | strace setgid call | §32.5 |

### 38.2 Capability Set

| Capability | Retained? | Primary Source | Section |
|-----------|----------|---------------|---------|
| `CAP_SYS_NICE` | YES | strace capset (final, post-drop) | §4.2, §32.5 |
| `CAP_NET_BIND_SERVICE` | YES | strace capset (final, post-drop) | §4.2, §32.5 |
| `CAP_CHOWN` | NO (REJECTED) | Capability audit; pre-drop only | §7.2, §32.4 |
| `CAP_DAC_OVERRIDE` | NO | Pre-drop only | §32.4 |
| `CAP_SETGID` | NO | Pre-drop only (needed for setgid; dropped after) | §32.4 |
| `CAP_SETUID` | NO | Pre-drop only (needed for setuid; dropped after) | §32.4 |

### 38.3 Socket and IPC

| Value | Description | Section |
|-------|-------------|---------|
| `/run/finchrender/coordinator.sock` | Main coordinator UNIX socket | §4.3, §32.6 |
| AF_UNIX SOCK_STREAM | Socket type and family | §4.3, §32.6 |
| backlog=128 | listen() backlog | §4.3, §32.6 |
| `/run/finchrender/coordinator-mgmt.sock` | Management socket | §23.1, §28.2 |

### 38.4 Cache and Filesystem

| Path | Access | Source | Section |
|------|--------|--------|---------|
| `/var/cache/finchrender/tiles` | DIR, read | strace openat + lsof fd 6 | §32.7, §33.2 |
| `/var/cache/finchrender/frames` | DIR, read | strace openat + lsof fd 7 | §32.7, §33.2 |
| `/var/cache/finchrender/shaders` | DIR, read | strace openat + lsof fd 8 | §32.7, §33.2 |
| `/proc/sys/kernel/shmmax` | read | strace openat + lsof fd 9; dossier §3 | §14.2, §32.6, §35.3 |
| `/dev/dri/renderD128` | rw | strace openat + lsof fd 10; dossier §5 | §5.3, §32.7 |
| `/sys/class/drm` | read | strace openat + lsof fd 11; dossier §6 | §6.3, §32.7 |

### 38.5 Environment Variables

| Variable | Value | Source | Section |
|----------|-------|--------|---------|
| `FINCHRENDER_TILE_WORKERS` | `8` | strace execve envp | §4.5, §10 |
| `FINCHRENDER_FRAME_BUFFER_MB` | `512` | strace execve envp | §4.5, §10 |
| `FINCHRENDER_SOCKET_TIMEOUT` | `30` | strace execve envp | §4.5, §10 |
| `FINCHRENDER_LOG_LEVEL` | `info` | strace execve envp | §4.5, §10 |

### 38.6 File Descriptor Bound

| Value | Description | Source | Section |
|-------|-------------|--------|---------|
| 13 | Steady-state FD count | lsof steady-state.lsof (minus cwd/rtd/txt/mem) | §4.4, §33.5 |
| 15 | Under-load FD count | lsof under-load.lsof | §4.4, §14.3, §33.5 |
| 15 | Maximum FD bound | Dossier §4.4, established in INC-2024-0033 | §14.3 |

### 38.7 tmpfiles.d Requirements

| Entry | Path | Mode | Owner | Section |
|-------|------|------|-------|---------|
| `d` | `/run/finchrender` | 0755 | finchrender:render | §6.2, §26.3 |
| `D` | `/var/cache/finchrender/tiles` | 0750 | finchrender:render | §6.2, §26.3 |
| `D` | `/var/cache/finchrender/frames` | 0750 | finchrender:render | §6.2, §26.3 |
| `D` | `/var/cache/finchrender/shaders` | 0750 | finchrender:render | §6.2, §26.3 |

---

*End of Document — FinchRender Coordinator Operations Dossier*  
*Document ID: FRCRD-OPS-001 | Revision 2.3 | 2024-10-15*


---

## Appendix D: Coordinator Environment Bootstrap Reference

### D.1 Complete /etc/passwd Entry

The `finchrender` user must be present in `/etc/passwd` with these exact values:

```
finchrender:x:2771:2001:FinchRender Coordinator:/var/lib/finchrender:/usr/sbin/nologin
```

Fields:
- Username: `finchrender`
- Password: `x` (shadow file, no interactive login)
- UID: `2771`
- GID: `2001` (primary group is `render`)
- GECOS: `FinchRender Coordinator` (human-readable description)
- Home directory: `/var/lib/finchrender`
- Shell: `/usr/sbin/nologin` (no interactive shell, non-login service account)

### D.2 Complete /etc/group Entry

The `render` group must be present in `/etc/group` with these exact values:

```
render:x:2001:finchrender
```

Fields:
- Group name: `render`
- Password: `x` (shadow file)
- GID: `2001`
- Members: `finchrender` (the coordinator service account is a member of its own primary group)

The gateway service account (`finchrender-gw`, uid 2772) and cache manager service account
(`finchrender-cache`, uid 2773) are also members of the `render` group to allow them to
connect to the coordinator socket (which has mode 0660 with group `render`).

Full production `/etc/group` entry:
```
render:x:2001:finchrender,finchrender-gw,finchrender-cache
```

### D.3 Directory Ownership Reference

All directories that must be created and owned by the coordinator's service account:

| Path | Type | Owner | Group | Mode | Created By |
|------|------|-------|-------|------|-----------|
| `/run/finchrender` | socket dir (tmpfs) | finchrender | render | 0755 | tmpfiles.d `d` |
| `/var/cache/finchrender` | cache root | finchrender | render | 0750 | Ansible |
| `/var/cache/finchrender/tiles` | tile cache | finchrender | render | 0750 | tmpfiles.d `D` |
| `/var/cache/finchrender/frames` | frame cache | finchrender | render | 0750 | tmpfiles.d `D` |
| `/var/cache/finchrender/shaders` | shader cache | finchrender | render | 0750 | tmpfiles.d `D` |
| `/var/log/finchrender` | log directory | finchrender | render | 0750 | Ansible |
| `/var/lib/finchrender` | home/state dir | finchrender | render | 0750 | Ansible |
| `/var/lib/finchrender/checkpoints` | checkpoint dir | finchrender | render | 0750 | Ansible |
| `/etc/finchrender` | config dir | root | root | 0755 | Ansible |

Note: `/run/finchrender` is on a tmpfs and is recreated on every boot. The `d` directive
in tmpfiles.d ensures it exists with correct ownership before the coordinator starts.
All other directories are on persistent storage and are created once by the Ansible
provisioning playbook.

### D.4 Kernel Parameter Requirements

The following kernel parameters must be set on the coordinator host:

```
# /etc/sysctl.d/99-finchrender.conf
# FinchRender coordinator kernel parameter requirements

# Shared memory ceiling: must be >= 67108864 (64 MB)
# Required for the coordinator's GPU thumbnail shared memory pipeline
# See INC-2022-0034 for history
kernel.shmmax = 67108864

# Shared memory total: must be large enough for the thumbnail pipeline
# (64 MB per coordinator instance + overhead)
kernel.shmall = 65536

# File descriptor limit (soft): coordinator typically uses ~15; set ceiling higher
fs.file-max = 131072
```

These are applied via `sysctl -p /etc/sysctl.d/99-finchrender.conf` during provisioning
and are persistent across reboots.

### D.5 Device Permission Reference

The GPU render device must have the correct permissions before the coordinator starts:

```bash
# Set by Ansible provisioning playbook; verified in post-upgrade checklist
chown root:render /dev/dri/renderD128
chmod 0660 /dev/dri/renderD128
```

The coordinator inherits access to `/dev/dri/renderD128` through its `render` group membership.
The systemd `DeviceAllow` directive additionally allows access at the cgroup level.

If the device node number changes after a kernel upgrade (major.minor may change), the
`DeviceAllow` directive will still work because it matches by path, not by device number.
Verify after kernel upgrades: `stat /dev/dri/renderD128 | grep 'Device type'`.

---

## Appendix E: Acceptance Tests for Migration Validation

The following acceptance tests must pass before the systemd migration is declared complete:

**AT-01: Coordinator starts via systemd**  
`systemctl start finchrender` completes without error; `systemctl is-active finchrender` returns `active`.

**AT-02: Coordinator runs as finchrender:render**  
`systemctl show finchrender --property=MainPID` gives PID; `/proc/PID/status` shows
`Uid: 2771 2771 2771 2771` and `Gid: 2001 2001 2001 2001`.

**AT-03: Post-drop capability set is exactly CAP_SYS_NICE and CAP_NET_BIND_SERVICE**  
`cat /proc/PID/status | grep CapEff` gives a hex value; decoded with `capsh --decode=X`
must show exactly `cap_net_bind_service,cap_sys_nice`.

**AT-04: Socket exists with correct permissions**  
`stat /run/finchrender/coordinator.sock` shows type socket, owner `finchrender:render`, mode `0660`.

**AT-05: tmpfiles.d directories created with correct ownership**  
`stat /run/finchrender` shows dir, owner `finchrender:render`, mode `0755`.
`stat /var/cache/finchrender/tiles` shows dir, owner `finchrender:render`, mode `0750`.
Same for `frames` and `shaders`.

**AT-06: GPU device accessible**  
After coordinator start, check logs for GPU enumeration success.
`ls /sys/class/drm/` shows DRM device entries.
`stat /dev/dri/renderD128` shows device, owner `root:render`, mode `0660`.

**AT-07: All workers reconnect**  
After coordinator restart, `frc_workers_connected` metric reaches 14 within 5 minutes.

**AT-08: Job submit and complete**  
Submit a single-tile test render job; verify it completes and the output tile appears in
`/var/cache/finchrender/tiles/`.

**AT-09: Coordinator restarts on failure**  
Kill coordinator with `kill -KILL PID`; verify systemd restarts it within 10 seconds
(`systemctl show finchrender --property=ActiveState` transitions from `failed` to `active`).

**AT-10: No stale socket after restart**  
After the AT-09 kill-and-restart, verify `/run/finchrender/coordinator.sock` exists and
accepts new connections (no ENOENT or EADDRINUSE errors in coordinator logs).

---

*End of Appendices — FinchRender Coordinator Operations Dossier*


---

## Appendix F: Coordinator Binary Verification and Integrity Checks

### F.1 Binary Hash Verification

Before deploying a new coordinator binary, verify its SHA-256 hash against the release
artifact published in the FinchRender release notes:

```bash
# Verify current binary
sha256sum /usr/local/bin/finchrender-coordinator

# Expected format: <64-hex-char-hash>  /usr/local/bin/finchrender-coordinator
# Compare against the hash in the release notes for the version being deployed
```

Binary verification must be completed before running any of the acceptance tests in
Appendix E. A mismatch indicates either a corrupted download or a version mismatch.

### F.2 Startup Log Verification

After any coordinator startup, verify the following log lines appear in the first 5 seconds
of the log stream (accessible via `journalctl -u finchrender -f --since=now`):

```
[INFO] finchrender-coordinator starting, version=2.0.4
[INFO] configuration loaded: user=finchrender group=render socket=/run/finchrender/coordinator.sock
[INFO] shmmax check passed: current=67108864 minimum=33554432
[INFO] privilege drop complete: uid=2771 gid=2001
[INFO] capset: effective=CAP_SYS_NICE|CAP_NET_BIND_SERVICE permitted=CAP_SYS_NICE|CAP_NET_BIND_SERVICE inheritable=0x0
[INFO] socket bound: /run/finchrender/coordinator.sock
[INFO] GPU enumeration: found 1 render device(s) at /dev/dri/renderD128
[INFO] cache directories opened: tiles frames shaders
[INFO] coordinator ready; entering event loop
```

If any of these lines is absent or shows different values (e.g., wrong uid, wrong capabilities,
wrong socket path), the deployment should be rolled back immediately.

### F.3 Capability Verification Script

The following shell script verifies the coordinator's post-drop capability set programmatically.
It can be run as part of the post-upgrade checklist:

```bash
#!/bin/bash
# verify-caps.sh — verify finchrender-coordinator capability set
set -euo pipefail

PID=$(pgrep -x finchrender-coordinator) || { echo "ERROR: coordinator not running"; exit 1; }
STATUS_FILE="/proc/$PID/status"

# Extract CapEff hex value
CAP_EFF=$(grep '^CapEff:' "$STATUS_FILE" | awk '{print $2}')

# Expected: CAP_SYS_NICE (bit 23, 0x800000) | CAP_NET_BIND_SERVICE (bit 10, 0x400)
# Combined: 0x0000000000800400
EXPECTED="0000000000800400"

if [ "$CAP_EFF" = "$EXPECTED" ]; then
    echo "OK: CapEff=$CAP_EFF (CAP_SYS_NICE|CAP_NET_BIND_SERVICE)"
else
    echo "ERROR: CapEff=$CAP_EFF, expected $EXPECTED"
    echo "Decoded: $(capsh --decode=$CAP_EFF 2>/dev/null || echo 'capsh not available')"
    exit 1
fi
```

Save this script to `/usr/local/bin/verify-coordinator-caps.sh` and run it after each
coordinator deployment as part of the post-upgrade validation procedure (Section 9.2, step 3).

### F.4 FD Count Monitoring Script

The following script provides a quick snapshot of the coordinator's open file descriptors,
suitable for ad-hoc monitoring or for inclusion in a pre-upgrade checklist:

```bash
#!/bin/bash
# check-coordinator-fds.sh — check finchrender-coordinator open fd count
set -euo pipefail

PID=$(pgrep -x finchrender-coordinator) || { echo "ERROR: coordinator not running"; exit 1; }
FD_COUNT=$(ls /proc/$PID/fd | wc -l)
FD_BOUND=15

echo "Coordinator PID: $PID"
echo "Open FD count: $FD_COUNT (bound: $FD_BOUND)"

if [ "$FD_COUNT" -le "$FD_BOUND" ]; then
    echo "STATUS: OK"
else
    echo "STATUS: WARNING - FD count exceeds expected bound"
    echo "Full lsof:"
    lsof -p "$PID" -n -P
fi
```

Run this script if the Prometheus `frc_open_fds` alert fires or as part of the post-upgrade
validation procedure (replacing the manual lsof check in Section 9.2).

---

*End of Appendix F*

*Total dossier length: Sections 1-38 plus Appendices A-F.*  
*Maintained by Platform Engineering | Revision 2.3 | 2024-10-15*


---

*Document Control Note: This dossier is the authoritative reference for the FinchRender
Coordinator systemd migration. All implementation decisions should be traced back to sections
of this document. Discrepancies between this document and any other documentation source
should be resolved in favor of this dossier, which is maintained by the Platform Engineering
team and reflects the most recent operational observations and audit findings.*
