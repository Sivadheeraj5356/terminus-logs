Service specification

Bring the appliance into operation entirely through host administration. Nothing here requires changing the compiled daemon.

This specification is split across two files. This file, /app/SPEC.md, is the host administration contract: the service account, the filesystem, the configuration file, the address pools, log rotation, the scheduled jobs, hardening, and the command privilege rules. The administrative commands and the daemon request format are in /app/COMMANDS.md. /app/README.md describes the provided daemon.

Service account

Create a system group named dhcpd and a system user named dhcpd whose numeric id is below 1000, whose primary group is dhcpd, whose home directory is /var/lib/dhcpd, and whose shell is a non login shell.

Filesystem

The state directory /var/lib/dhcpd and the log directory /var/log/dhcpd are owned by the dhcpd user and group with mode 0750. The lease database /var/lib/dhcpd/dhcp.db is created from /opt/dhcpd/share/schema.sql, owned by the dhcpd user and group, and closed to other users, so mode 0640 or stricter. The backup directory /var/lib/dhcpd/backups is owned by the dhcpd user and group with mode 0700 and holds database snapshots that other users cannot read. Pool definition files live in /etc/dhcpd/pools.d, and each one is a JSON document whose name ends in .json; the tooling loads only files with that extension, so a pool declared under any other name is ignored. An example pool file that shows the format and the .json naming ships at /app/examples/pool.example.json.

Configuration file

/etc/dhcpd/dhcpd.conf is a single file of key and value lines that every administrative command reads. It declares at least STATE_DB as /var/lib/dhcpd/dhcp.db, POOL_DIR as /etc/dhcpd/pools.d, LOG_DIR as /var/log/dhcpd, and BACKUP_DIR as /var/lib/dhcpd/backups, and it may set BACKUP_KEEP. Each command resolves a path from its environment variable when one is set, namely DHCPD_DB, DHCPD_POOLS_DIR, or DHCPD_BACKUP_DIR, otherwise from this file, otherwise from a built in default. These environment overrides are authoritative and must stay in effect for the command that actually runs, including DHCPD_BACKUP_KEEP and the DHCPD_NOW_MS clock override. A caller may point any command at a scratch database or directory through these variables, so a command that drops privileges to the service account must carry them across that boundary rather than letting them be discarded. Re executing under sudo, su, or runuser with a sanitised environment silently loses an injected DHCPD_DB and makes the command act on the wrong database, so preserve these variables when changing user.

Preserving the variable is not by itself enough. A scratch path a caller injects is owned by that caller, for example the root owned scratch database the acceptance harness creates, and once a command has dropped to the dhcpd account it can no longer read or write that path. Therefore, when DHCPD_DB or another override points at a path the caller owns rather than the dhcpd account, the command must not drop privileges at all but operate on that path as the caller. A command that does drop privileges for its default live paths must perform every read and write on caller supplied override paths before the drop. The plain and reliable choice is not to change user inside the commands and to let cron and logrotate run the scheduled work as the dhcpd account.

Pools

Every pool below is declared as a create_pool request document, in the shape given under the daemon request format, in its own .json file under /etc/dhcpd/pools.d, and loaded into the live database, and no other pools may be present. The live database holds no leases, declines, or other state beyond these pool definitions and their reservations, so do not leave behind leases from your own testing. The site network is 10.10.0.0/24 with 3600 second leases, the address 10.10.0.1 withheld from allocation, and 10.10.0.10 reserved for the client printer. The guest network begins at 10.20.0.0 and is sized to offer at least one thousand usable addresses, so a twenty two bit prefix or larger, with 600 second leases and the gateway 10.20.0.1 withheld from allocation. The voip network is 10.30.0.0/24 with 86400 second leases, the address 10.30.0.1 withheld from allocation, and 10.30.0.5 reserved for the client pbx.

Log rotation

/etc/logrotate.d/dhcpd rotates the files matching /var/log/dhcpd and ending in log daily, keeps at least fourteen rotations, compresses rotated logs, tolerates a missing log, and rotates as the dhcpd account, and the configuration parses cleanly.

Scheduled maintenance

From the system crontab under /etc/cron.d, and running as the dhcpd account, schedule dhcpd-reap to clear expired leases, dhcpd-backup to take a periodic snapshot, dhcpd-report with its output appended to a log under /var/log/dhcpd, and dhcpd-provision --check to surface drift with its output appended to a log under /var/log/dhcpd.

Hardening and integrity

The live database runs in write ahead logging mode. /etc/security/limits.d/dhcpd.conf declares a nofile limit and a nproc limit for the dhcpd account. Nothing anywhere under /var/lib/dhcpd is accessible by other users. The maintenance commands that change state, namely dhcpd-provision, dhcpd-backup, dhcpd-restore, and dhcpd-renumber, append a line to an audit log at /var/log/dhcpd/admin.log, owned by the dhcpd user and group with mode 0640, and each line names the command that ran verbatim, so the log can be searched for a command by its own name.

Advanced maintenance and attestation

Three further commands are installed on the system path alongside the others. dhcpd-renumber moves a pool to a new address range, re-homing its state. dhcpd-audit reconciles the live tables against the pool ranges and reservations and can fail on any inconsistency. dhcpd-verify prints a canonical, HMAC signed manifest of the database state so a deployment can be attested and two databases compared byte for byte. Their exact behaviour and the manifest format are in /app/COMMANDS.md.

Operator delegation

A system group named dhcpdops exists for operators who may run the read only maintenance commands but not otherwise administer the host. A sudoers policy file under /etc/sudoers.d grants members of dhcpdops the right to run only dhcpd-report, dhcpd-verify, dhcpd-audit, dhcpd-fsck, dhcpd-check, and dhcpd-provision with the --check flag, and only as the dhcpd account, without a password, and grants nothing else. The state changing commands dhcpd-backup, dhcpd-restore, dhcpd-reap, dhcpd-renumber, and an unqualified dhcpd-provision are not delegated. The policy file is mode 0440 and parses cleanly under visudo.
