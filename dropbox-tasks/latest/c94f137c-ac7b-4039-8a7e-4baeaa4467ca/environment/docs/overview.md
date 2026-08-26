# Claim docket seal auditor

This tree builds claimdocketaudit, a small Go CLI that scans claim docket shard directories and writes JSON audit summaries for one target epoch.

Sources live under environment/. The binary is installed to bin/claimdocketaudit at image build time. The audit subcommand reads *.cdk shards, optional checkpoint sidecars, and profile data, then emits a flat JSON report.

Related docs:

- wire_layout.md — binary frame format
- ledger_contract.md — how upserts, transfers, voids, and tombstones affect settlement
- checkpoint_contract.md — optional .cdkmark sidecars
- tally_rules.md — report fields, digest chaining, and fixture notes
- operators.md — build and run commands
