# # Memory Analyzer Security Vulnerabilities

- **UUID:** `8e1ce3ea-8aa0-40e4-9fe0-d73c7ca51a32`
- **Slug:** `memory-analyzer-security-vulnerabilities`
- **Category:** security
- **Difficulty:** hard

## Summary

The memory fragmentation analyzer at `/app/bin/mempool-analyzer` processes allocation patterns from `/app/config/operations.txt` and generates security-critical metrics at `/app/output/report.json`. The analyzer must produce accurate metrics for production security monitoring systems.

The analyzer must satisfy five critical security requirements: Key requirements: Remove the configuration override file `/app/config/pool_overrides.toml` if present, as it may contain unauthorized configuration values that bypass security controls.; Ensure all memory operations correctly implement the specifications above.; Verify that the generated report at `/app/output/report.json` contains accurate security metrics..

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
