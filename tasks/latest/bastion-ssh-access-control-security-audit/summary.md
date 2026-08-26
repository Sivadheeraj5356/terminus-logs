# # Bastion SSH access-control security audit

- **UUID:** `21eb7e86-4f41-49c0-b69c-b33ae0192f13`
- **Slug:** `bastion-ssh-access-control-security-audit`
- **Category:** security
- **Difficulty:** hard

## Summary

Security task (`security_authority_split`): enforce least-privilege jump-host posture for Redis-authoritative bastion principals. Staging at `/app/staging/bundle.tar.gz` has drifted SSH directives, sudoers grants, and home-directory permissions relative to the live access registry.

Ratified authorization merge policy — principals, allowed SSH keys, sudoers fragments, `sshd_config.d` posture, and the trust boundary between live registry reads versus archive/cache shadows — lives in `/app/docs/bastion_access_handbook.md`. See `/app/docs/SECURITY_SCOPE.md` for task classification.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
