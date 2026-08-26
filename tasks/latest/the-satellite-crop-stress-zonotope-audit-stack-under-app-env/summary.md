# The satellite crop-stress zonotope audit stack under /app/environment regenerate

- **UUID:** `088d2445-fc50-4f80-9c6e-83cdcecf6b6d`
- **Slug:** `the-satellite-crop-stress-zonotope-audit-stack-under-app-env`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The satellite crop-stress zonotope audit stack under /app/environment regenerates /app/output/audit_report.json through the published runner. Default lanes can look coherent in stage echoes, then the terminal audit drifts under watermark-bound journal replay and rotation remaps: lane digests and floating-point nest spans disagree with the stage echo, cold regenerations drift across reruns if stage residue survives, a warm restart can diverge from the cold baseline, and history CHK blocks above the watermark (or compaction echoes beside the journal) appear to drive numerical digests when they should not.

Do not hand-write the JSON; rebuild through the published runner. /app/environment/tools/hs_run.sh --all-lanes --rotations /app/environment/docs/rot_d.toml

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
