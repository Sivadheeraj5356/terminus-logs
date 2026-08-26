# `/app/bin/windowjudge.js` replays one recorded HSM ceremony stream. It reads one

- **UUID:** `ea62cbb7-280a-4ca6-9758-7f3620245a6a`
- **Slug:** `app-bin-windowjudge-js-replays-one-recorded-hsm-ceremony-str`
- **Category:** security
- **Difficulty:** hard

## Summary

`/app/bin/windowjudge.js` replays one recorded HSM ceremony stream. It reads one JSON document on stdin and writes exactly `{"intervals":[...]}` on stdout.

Each interval has `start`, `end`, `reason`, and exactly one actor field, `key`, `package`, `sensor`, or `player`; if no windows are confirmed, `intervals` is an empty array. The input has `until`, `events`, and exactly one top-level mode array: `keys`, `packages`, `sensors`, or `players`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
