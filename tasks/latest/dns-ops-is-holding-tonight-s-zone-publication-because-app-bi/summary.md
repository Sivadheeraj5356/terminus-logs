# DNS ops is holding tonight’s zone publication because `/app/bin/zone-publisher`

- **UUID:** `1a4146a3-efdf-491c-956e-6853644a80b8`
- **Slug:** `dns-ops-is-holding-tonight-s-zone-publication-because-app-bi`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

DNS ops is holding tonight’s zone publication because `/app/bin/zone-publisher` is giving the wrong answer on a few reviewed change batches. The command takes `--zone`, `--journal`, `--freezes`, `--exceptions`, and `--report`; it should validate the candidate zone and write the publication report described in `/app/docs/`.

Please repair the Ruby implementation under `/app` so valid batches return the right publish/block status, the report is deterministic, and fatal input problems exit cleanly without replacing an existing report. Keep stdout empty; stderr is only for fatal errors.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
