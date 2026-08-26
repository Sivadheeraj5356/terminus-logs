# We need a native security audit tool for a small infrastructure repo. Write a C

- **UUID:** `1654ef48-8ee1-4548-9145-f218d1d02eb9`
- **Slug:** `we-need-a-native-security-audit-tool-for-a-small-infrastruct`
- **Category:** security
- **Difficulty:** hard

## Summary

We need a native security audit tool for a small infrastructure repo. Write a C program, build a compiled executable named `policy-auditor`, and use it to scan `/app/task_file/input_data/repo/` for risky production access policies; the default output must be `/app/task_file/output_data/findings.sarif`, and the executable must also support `policy-auditor <repo_dir> <sarif_output>`.

Successful runs must return exit code 0 and write nothing to stderr. The output is exact-match SARIF 2.1.0 shape: top-level `version` is `2.1.0`, `$schema` is `https://json.schemastore.org/sarif-2.1.0.json`, `runs[0].tool.driver.name` is non-empty, `runs[0].tool.driver.rules` is non-empty, and each result has `ruleId`, `message.text`, `locations[0].physicalLocation.artifactLocation.uri` as a path relative to the scanned repo with no leading slash, and `locations[0].physicalLocation.region.startLine` as a 1-based integer.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
