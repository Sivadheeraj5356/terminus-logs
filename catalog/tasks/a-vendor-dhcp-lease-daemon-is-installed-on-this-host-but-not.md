# A vendor DHCP lease daemon is installed on this host but not yet configured to o

Submission: `129609c5-417c-4a62-8b34-4c9e9861d442`  
Slug: `a-vendor-dhcp-lease-daemon-is-installed-on-this-host-but-not`  
Latest archive: `129609c5-417c-4a62-8b34-4c9e9861d442_submission_2026-07-21T07_46_16.731Z.zip`  
Revisions in Dropbox: 22

## Task summary

A vendor DHCP lease daemon is installed on this host but not yet configured to operate. Do not change the daemon. Bring the lease service into full production through host administration. Its state lives in the SQLite database named by DHCPD_DB, default /var/lib/dhcpd/dhcp.db. A correct host runs the service under a dedicated unprivileged dhcpd account and group, never root. It writes the config file /etc/dhcpd/dhcpd.conf that every command reads for the database and its pool, log, and backup directories. Those directories under /var/lib/dhcpd and /var/log/dhcpd are private to the account, and the lease database, built from the shipped schema, is owned by it and closed to others. It installs the control and maintenance commands on the system path and provisions the three required address pools under /etc/dhcpd/pools.d and no others, leaving the database clean.

Required artifacts include: `/app/SPEC.md`, `/app/COMMANDS.md`, `/app/README.md`.

Author anonymous tagged this **hard** system-administration task (dhcp, service-hardening, reconciliation, integrity-check, backup-restore, attestation).

Time estimates: expert ~100 min, junior ~280 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `129609c5-417c-4a62-8b34-4c9e9861d442_submission_2026-07-21T07_46_16.731Z.zip` is a task submission, not a Harbor job. 22 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
