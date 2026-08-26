# # Booking Slot Merge

- **UUID:** `2939c523-a9c0-4197-aac6-3849160e4ac2`
- **Slug:** `booking-slot-merge`
- **Category:** debugging
- **Difficulty:** hard

## Summary

`slot-merge` coalesces room and resource booking intervals stored as JSONL in `*.slot` files. The verifier rebuilds `/app/target/release/slot-merge` from your source after you edit it.

Output from the tool does not always match the rules below.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
