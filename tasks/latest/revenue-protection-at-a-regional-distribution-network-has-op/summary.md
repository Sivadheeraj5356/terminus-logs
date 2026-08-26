# Revenue protection at a regional distribution network has opened a meter-fraud c

- **UUID:** `3c219701-ea00-430f-8254-e5e0dbed8b93`
- **Slug:** `revenue-protection-at-a-regional-distribution-network-has-op`
- **Category:** security
- **Difficulty:** hard

## Summary

Revenue protection at a regional distribution network has opened a meter-fraud case, and our firm has the forensic audit. Field crews keep pulling tapped service heads off circuits whose exports look clean, the same meter credential keeps turning up at delivery points minutes apart, and a run of settlement disputes has been quietly writing off charges that should have stood.

The seized evidence sits in a corpus shaped like /app/data: the network registry, the utilities' raw binary meter exports under exports/, the regulator's circular book under circulars/, and the disputes file. The board wants a case report it can reproduce on any corpus, and a review service the tribunal can read the closed case through.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
