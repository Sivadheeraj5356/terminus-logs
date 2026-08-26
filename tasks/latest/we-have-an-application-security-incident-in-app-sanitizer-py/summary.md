# We have an application-security incident in `/app/sanitizer.py`: the gateway's i

- **UUID:** `e291e403-f7f7-493d-9804-6284c93e57de`
- **Slug:** `we-have-an-application-security-incident-in-app-sanitizer-py`
- **Category:** security
- **Difficulty:** hard

## Summary

We have an application-security incident in `/app/sanitizer.py`: the gateway's input firewall is vulnerable to parser differential attacks, active URL-scheme smuggling, prototype-pollution key injection, and Unicode spoofing at a trust boundary. Patch the vulnerable security control and add the missing SQLite decision ledger used by incident responders.

The default files remain `/app/input.jsonl`, `/app/policy.json`, `/app/output.jsonl`, `/app/rejected.jsonl`, and `/app/security_audit.sqlite`. Keep the existing CLI overrides and add `--audit-db` for the ledger path.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
