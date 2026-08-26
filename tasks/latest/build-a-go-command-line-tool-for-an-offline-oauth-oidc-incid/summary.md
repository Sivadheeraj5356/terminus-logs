# Build a Go command line tool for an offline OAuth/OIDC incident review. It needs

- **UUID:** `441f5efc-b7ab-4668-b49c-9bf0d34b26c6`
- **Slug:** `build-a-go-command-line-tool-for-an-offline-oauth-oidc-incid`
- **Category:** security
- **Difficulty:** hard

## Summary

Build a Go command line tool for an offline OAuth/OIDC incident review. It needs to replay a token-exchange ledger, report the active exposure at the review timestamp, and choose the canonical bounded remediation plan.

Keep source at `/app/task_file/src/token_audit.go` and build `/app/task_file/bin/token_audit`. Run it exactly as `--input <case-file> --output <report-file>` in that order, with no extra arguments.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
