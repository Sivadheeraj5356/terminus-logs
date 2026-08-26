# Memory Vault is a scored dungeon-crawl text adventure. Players walk rooms,

- **UUID:** `282b53e2-9b37-4be3-9ec1-548e08817733`
- **Slug:** `memory-vault-is-a-scored-dungeon-crawl-text-adventure-player`
- **Category:** games
- **Difficulty:** hard

## Summary

Memory Vault is a scored dungeon-crawl text adventure. Players walk rooms, TAKE and DROP items, WAIT to ready a seal, SEAL watched chambers, SCRUB leak chambers, and EXIT with the key for WIN, LOSE, or PARTIAL endings.

Campaign playthrough scripts live under `/app/environment/cases`. The adventure under `/app/environment` must score those playthroughs using the live chamber ledgers in `/app/environment/traces/` and write the campaign scoreboard: `/app/output/transcripts/<case_id>.json`, `/app/output/state/hazard.epoch`, `/app/output/state/replay.journal`, and `/app/output/batch.manifest.json`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
