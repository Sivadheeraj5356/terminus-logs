# specification_archaeology

- **UUID:** `4018aa09-b19d-47fe-a6cd-cc1aed10ad53`
- **Slug:** `specification-archaeology`
- **Category:** security
- **Difficulty:** hard

## Summary

Security engineering needs a defensible containment decision for four incident cases. The evidence under `/app/environment/evidence`, case overlays under `/app/environment/cases`, and authority documents under `/app/environment/authorities` are the complete record.

Reconcile them using the public rules in those documents; filenames and record order carry no authority. Output-only work is allowed; no supplied application is broken.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
