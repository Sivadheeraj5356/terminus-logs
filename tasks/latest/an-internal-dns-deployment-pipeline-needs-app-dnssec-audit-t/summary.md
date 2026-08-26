# An internal DNS deployment pipeline needs `/app/dnssec-audit` to decide whether

- **UUID:** `9353db02-8890-4cf8-94fb-b5eaacb85392`
- **Slug:** `an-internal-dns-deployment-pipeline-needs-app-dnssec-audit-t`
- **Category:** security
- **Difficulty:** hard

## Summary

An internal DNS deployment pipeline needs `/app/dnssec-audit` to decide whether a child-zone delegation can be admitted without contacting the network. Complete the Go implementation in `/app` so the command reads one JSON bundle from the file named by its optional argument, or from standard input when no argument is supplied, and writes exactly one JSON object containing `admit` and `reasons`.

The detailed bundle schema and the canonical DNSSEC subset used by this pipeline are documented in `/app/POLICY.md`; that file is the behavioral authority for this task. Admission requires a supported parent DS to authenticate an eligible child DNSKEY and every supplied RRset to have a currently valid signature from an authenticated zone key.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
