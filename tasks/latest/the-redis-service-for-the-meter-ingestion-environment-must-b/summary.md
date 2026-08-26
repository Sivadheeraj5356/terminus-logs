# The Redis service for the meter ingestion environment must be brought into compl

- **UUID:** `2f5e899b-db87-448d-adf0-e88fc0d53a5b`
- **Slug:** `the-redis-service-for-the-meter-ingestion-environment-must-b`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The Redis service for the meter ingestion environment must be brought into compliance with the operations standard in /app/docs/redis-operations-standard.md, then populated from /app/input/redis-hardened-meter-fixtures.tar.gz using the supplied migration utility at /app/bin/import-fixtures.php. Work only with the local files and services in the container.

Apply the required changes to the existing Redis service and configuration described by the environment. The final Redis instance must be reachable on the interface and port approved by the standard, reject unauthenticated clients, expose only the approved ACL principals, disable the prohibited administrative commands, and use the required persistence locations and permissions.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
