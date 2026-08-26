# After an aborted write wave, lane A nat_key 10 still emits row_kind live on the

- **UUID:** `3a528f89-6e97-4907-a1ba-bf24238cfc77`
- **Slug:** `after-an-aborted-write-wave-lane-a-nat-key-10-still-emits-ro`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

After an aborted write wave, lane A nat_key 10 still emits row_kind live on the first H6 dual cred chain even though seg_lane_a_seed.jsonl already holds a void row for that key with sweep_gen five and a lower evt_stamp than the live row. Void entries remain in the seg and book fixture streams while a stale live row still wins pick.

A later dual chain without H6_RESET settles nat_key 10 to void. For that key the lane A checkpoint wit_fp disagrees with the emitted row wit_fp.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
