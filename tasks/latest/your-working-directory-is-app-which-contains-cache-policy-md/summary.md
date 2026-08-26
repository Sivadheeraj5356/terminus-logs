# Your working directory is /app, which contains cache_policy.md and tier.conf. Yo

- **UUID:** `dbf97970-aede-47d5-8b42-417a1682f883`
- **Slug:** `your-working-directory-is-app-which-contains-cache-policy-md`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Your working directory is /app, which contains cache_policy.md and tier.conf. You are provisioning read delegation for the eight build-artifact caches under /srv/ci-cache, using the real account tools (chown, chgrp, chmod, setfacl).

The full model is in /app/cache_policy.md and the budgets and settle delay are in /app/tier.conf. The caches ship bare and owned by root.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
