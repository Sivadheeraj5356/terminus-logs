# The work is the administration of the Aldreth county deeds registry host. It

- **UUID:** `6c09ccf7-244a-413d-b3c3-534d5d8fdf19`
- **Slug:** `the-work-is-the-administration-of-the-aldreth-county-deeds-r`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The work is the administration of the Aldreth county deeds registry host. It covers the charges recorded upon the titles the registry enrolls, the register of charges in force, the muniment room of enrolled deeds, the registrar's seal, the custody of the registry, and the standing of a deputy registrar whose engagement the county has ended.

The registry's standing orders, the county minute book, and a host reference are posted in the press at `/opt/registry/press`, together with a note left by the departed deputy. The standing orders and the minute are the sole authority for which charges stand in force; the minute is read whole against each charge, for a charge entered stands until a satisfaction is entered upon it or the court vacates it, upon either of which it stands no longer, while a charge whose stay the court afterward discharged stands in force, a stay being a stopping of enforcement and not an ending, and a charge left under an unanswered requisition stands as no charge.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
