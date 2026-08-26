# Build a security auditor under /app that scores encrypted backup trustworthiness

- **UUID:** `a42dfd18-6e62-4b62-9a15-1bada2e83212`
- **Slug:** `build-a-security-auditor-under-app-that-scores-encrypted-bac`
- **Category:** security
- **Difficulty:** hard

## Summary

Build a security auditor under /app that scores encrypted backup trustworthiness against adversarial tampering. Twenty archive files live in /app/archives as archive_01.json through archive_20.json.

Security contracts are /app/contracts/TRUST_REPORT.md, /app/contracts/ARCHIVE_FORMAT.md, and /app/rules/escrow_matrix.yaml. Write /app/verdicts/backup_trust_report.json with cryptographic coverage gaps, unauthorized mutations, escrow integrity breaks, retention tampering, restore forgery, silent corruption, and adversarial resilience failures.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
