# A turn-based combat resolution lab under `/app/environment` is due for matrix ce

- **UUID:** `37f78793-f79b-4906-9389-cf758425343a`
- **Slug:** `a-turn-based-combat-resolution-lab-under-app-environment-is`
- **Category:** games
- **Difficulty:** hard

## Summary

A turn-based combat resolution lab under `/app/environment` is due for matrix certification across manifests `sc_m1` through `sc_m5` under profiles `strict_tick` and `loose_tick`, with activation sweeps up to depth 5. Text tails under `/app/environment/fixtures/log_txt/` and the interim tally at `/app/environment/fixtures/tmp/interim_tally.json` are local smoke only; certification is judged solely on the graded matrix artifact.

The certified deliverable is `/app/output/cmb_out.json` with `matrix_tag` `cmb_v2`, `violation_total` of `0`, and contract-correct `depth_limit`, `runs`, `cross_digest`, and `repeat_stamp`. Emit it through the lab's published pipeline: `bash /app/environment/scripts/build_lab.sh`, then `/app/bin/mdl_lab` (mirrored at `/app/environment/tools/mdl_lab/mdl_lab`) using the matrix invocation in `/app/environment/docs/lab_contract.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
