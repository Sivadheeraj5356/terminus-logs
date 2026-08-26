# Scientific-computing undersea WDM optical-channel and Raman-pump caselab under `

- **UUID:** `b019bbdc-3fdc-4a95-a630-057457614080`
- **Slug:** `scientific-computing-undersea-wdm-optical-channel-and-raman`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Scientific-computing undersea WDM optical-channel and Raman-pump caselab under `/app/environment`. On the chains in `/app/environment/docs/runbook.md`, `/app/output/replan_report.json`, `/app/output/lambda_trace.csv`, `/app/output/settle_score.tsv`, `/app/var/splicekit/pump_ledger.json`, `/app/var/splicekit/journal.jsonl`, and `splicectl status` disagree with each other and with independent replay of the fixtures under `/app/data/scenarios`.

Wavelength continuity, regenerator remux, Raman cool-residual carry across commits and idle spans, demand admission ordering, per-span capacity on every routed hop with gbps accumulated from earlier admissions in the same run, shortest-path tie-breaks, settlement shares, digest packing, journal generation with prior digest linkage, and cross-artifact agreement misfire across runs. Subsystem numeric policy is defined in `/app/environment/docs/contract.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
