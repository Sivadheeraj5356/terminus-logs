# Recover the Blender render-node profile controller from the incomplete files und

- **UUID:** `e56dc618-7e9e-4454-8ff2-34a782c9530a`
- **Slug:** `recover-the-blender-render-node-profile-controller-from-the`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Recover the Blender render-node profile controller from the incomplete files under /app. Make install must provide /usr/local/bin/blendprofile, the blendprofile-reconcile@.service systemd template, and the blendprofile tmpfiles policy.

The controller must safely create portable profiles, reconcile add-ons in dependency order, preserve generation history, and report configuration drift without repairing it. Support create --manifest PATH --root PATH --profile NAME --out PATH with optional --dry-run, and validate with the same required paths.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
