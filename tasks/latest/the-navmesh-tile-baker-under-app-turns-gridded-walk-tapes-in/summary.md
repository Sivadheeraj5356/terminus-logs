# The navmesh tile baker under `/app` turns gridded walk tapes into stitched tile

- **UUID:** `7e3911b7-a546-4134-937c-c6138037a4b5`
- **Slug:** `the-navmesh-tile-baker-under-app-turns-gridded-walk-tapes-in`
- **Category:** scientific-computing
- **Difficulty:** medium

## Summary

The navmesh tile baker under `/app` turns gridded walk tapes into stitched tile polygons with border portal links. Continuous matrix legs look healthy on quick inspection, but pause-resume legs on the same scenario drift: parity checks fail, border weld counts change, link digests diverge, and area overlays at tile seams disagree with their cold twin.

Pad-weighted tapes can also corrupt continuous digests when pad / resume state leaks into the weld. Rebuild through `/app/ci/build_and_load.sh` and emit `/app/output/nav_audit.json` matching `/app/doc/nav_audit_contract.txt`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
