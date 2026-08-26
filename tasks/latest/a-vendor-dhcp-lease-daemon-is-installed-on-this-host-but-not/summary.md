# A vendor DHCP lease daemon is installed on this host but not yet configured to o

- **UUID:** `129609c5-417c-4a62-8b34-4c9e9861d442`
- **Slug:** `a-vendor-dhcp-lease-daemon-is-installed-on-this-host-but-not`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

A vendor DHCP lease daemon is installed on this host but not yet configured to operate. Do not change the daemon.

Bring the lease service into full production through host administration. Its state lives in the SQLite database named by DHCPD_DB, default /var/lib/dhcpd/dhcp.db.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
