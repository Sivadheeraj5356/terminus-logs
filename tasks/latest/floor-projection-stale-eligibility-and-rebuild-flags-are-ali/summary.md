# Floor projection, stale eligibility, and rebuild flags are aligned, but `frontie

- **UUID:** `49b48b21-5c4d-46b9-9dad-6e88538027b6`
- **Slug:** `floor-projection-stale-eligibility-and-rebuild-flags-are-ali`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Floor projection, stale eligibility, and rebuild flags are aligned, but `frontier_digest_hex` still drifts and runtime or manifest changes mid-session are not fully reflected in the rebuilt report. Third milestone: finish the rebuild path so `/app/scripts/frontier.sh` and `/app/launcher/lf_align` produce identical fixture-consistent output keyed by every consumer id in `/app/data/manifest.json` at rebuild time.

Rechecks must pick up manifest rows and runtime settings changed during the session. Field summaries live in `/app/doc/frontier_fields.txt`; consolidation rules in `/app/doc/staleness_contract.txt`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
