# # Claim docket audit drift

- **UUID:** `c94f137c-ac7b-4039-8a7e-4baeaa4467ca`
- **Slug:** `claim-docket-audit-drift`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Replication QA reports the Go claim docket seal auditor under `/app/environment` no longer matches independent recomputation from fixture bytes on practice and regression trees. Repair sources under `/app/environment` so the normal pipeline regenerates `/app/out/claim_docket_audit.json`.

The verifier rebuilds `/app/bin/claimdocketaudit` from sources and reruns audits across fixture directories; hand-written JSON without that pipeline is insufficient. Do not edit `/tests`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
