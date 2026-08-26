DHCP lease appliance

This host ships a small DHCP style IPv4 lease daemon as a vendor appliance. The compiled daemon lives under /opt/dhcpd and is ready to run, but the host has not been configured to operate it. The work here is host administration. Stand the service up so it runs under its own account, keeps its state on disk under restrictive permissions, offers administrative and maintenance commands, serves several provisioned address pools, backs itself up, reports its utilisation, rotates its logs, and reaps expired leases on a schedule.

What ships in the image

The compiled lease daemon is at /opt/dhcpd/libexec/dhcpd and must not be modified, and the lease database schema is at /opt/dhcpd/share/schema.sql. The daemon is a one shot command. It reads a single JSON request document named on its command line, applies the operation, and writes one JSON reply. It keeps its state in the database named by the DHCPD_DB environment variable, which defaults to /var/lib/dhcpd/dhcp.db.

What you administer

A dedicated unprivileged account and group, private state, log, and backup directories owned by that account and closed to other users, and a lease database initialised from the shipped schema and owned by the account. The administrative and maintenance commands on the system path run a request, load pool definitions, clear expired leases, snapshot and recover the database, validate the deployment and the database, and report per pool utilisation. A configuration tree holds the pool definitions that are provisioned into the live database, a log rotation policy covers the service logs, and cron jobs run the maintenance on a schedule as the account.

The specification document gives the exact paths, ownership, permissions, command behaviour, the pools to provision, the log rotation and scheduling requirements, and the daemon request format.
