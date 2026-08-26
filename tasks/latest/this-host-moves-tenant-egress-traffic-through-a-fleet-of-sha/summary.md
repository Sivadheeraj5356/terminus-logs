# This host moves tenant egress traffic through a fleet of shaped network interfac

- **UUID:** `1ed09eb2-8e0c-4323-bfe1-8712ef6228b7`
- **Slug:** `this-host-moves-tenant-egress-traffic-through-a-fleet-of-sha`
- **Category:** system-administration
- **Difficulty:** medium

## Summary

This host moves tenant egress traffic through a fleet of shaped network interfaces, and every one of them needs its shaping policy provisioned from the link ledger registry. An active interface gets a unix group plus a nologin user with a fixed uid.

It also gets a state directory under /var/lib/link-rate that the user owns, a systemd-networkd drop-in under /etc/systemd/network and a policy environment file under /etc/link-rate.d. Detached interfaces get no account and nothing on disk, though their ledger rows still belong in the chain.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
