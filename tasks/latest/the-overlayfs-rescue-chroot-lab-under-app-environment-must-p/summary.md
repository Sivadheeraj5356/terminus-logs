# The overlayfs rescue chroot lab under `/app/environment` must produce a consiste

- **UUID:** `5d8a0bc1-9647-4168-8e6f-b1129c056ca8`
- **Slug:** `the-overlayfs-rescue-chroot-lab-under-app-environment-must-p`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The overlayfs rescue chroot lab under `/app/environment` must produce a consistent guard intersection across the public matrix. Training layouts (`train_a`, `train_b`) already look fine in smoke and in `/app/environment/kit/q9/q9_probe.json`, but held-out arms (`adv_c`, `adv_d`) still disagree on digests between the uninterrupted path and the recovered path, especially under whiteout or opaque merges, nested bind under chroot, and workdir/upperdir sibling checks.

Text tails under `/app/environment/kit/logs/` are incomplete; authoritative mount bytes live in `/app/environment/kit/blk/*.mnt`. Build with `bash /app/environment/scripts/build_all.sh`, then run `/app/environment/bin/og_check --full-matrix --out /app/output/invariant_proof_log.json`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
