# Build an underwater habitat supply chain planner under /app that compiles missio

- **UUID:** `ea3fa5f7-0a2b-46a8-af2a-9aae178000be`
- **Slug:** `build-an-underwater-habitat-supply-chain-planner-under-app-t`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Build an underwater habitat supply chain planner under /app that compiles mission cargo into a reproducible resupply build pipeline. The pipeline ingests mission workload under /app/data/mission, materializes dependency-ordered staging artifacts under /app/state through tide timing, berth assignment, cargo priority, cold-storage limits, lane window rules, and transfer certification, then exports deterministic resupply-plan.json and utilization-report.json under /app/output.

Implement the habitat-resupply-ingest and habitat-resupply-export command-line tools: habitat-resupply-ingest reads the mission directory and writes validated staging artifacts; habitat-resupply-export compiles only certified staging into final build outputs without reopening raw mission inputs. Ingest must write seven staging files under /app/state: tide-snapshot.json, rov-index.json, berth-staging.json, transfer-cert.json, export-bind.json, o2-priority-freeze.json, and ingest-manifest.json.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
