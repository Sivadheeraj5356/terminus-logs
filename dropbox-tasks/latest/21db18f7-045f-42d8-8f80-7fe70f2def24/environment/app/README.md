# flaky-repro

Internal QA tooling for investigating flaky Playwright end-to-end test failures.
Built by the platform-eng team for use by QA engineers during release stabilization.

## Background

After the v2.0 retry-policy refactor, we started logging rerun sessions separately
from original sessions. The historical aggregation and reporting utilities were updated
incrementally across several CI cycles and have accumulated some drift.

## Usage

```bash
# Generate historical prioritization report
node cli.js report

# Generate a Playwright reproduction plan for the top flaky specs
node cli.js plan --session plan-sess-$(date +%s)

# Execute the plan and produce an execution report
node cli.js run --session plan-sess-$(date +%s)
```

Output files are written to `/app/logs/`.

## Structure

```
cli.js                  # Main CLI entry
lib/                    # Report, plan, and execution modules
db/
  history.db            # SQLite database (seeded at build time)
scripts/
  seed_db.js            # DB seeding script
config/
  playwright.base.js    # Base Playwright configuration reference
logs/                   # Output directory (report.json, plan.json, etc.)
```

## Database Schema

- `test_runs`: Historical Playwright test outcomes per spec/browser/session
- `browser_projects`: Browser-specific project configs (worker count, shards, retry settings)
- `execution_results`: Results from reproduction run executions

Several subsystems still need reconciliation after the v2.0 schema and cache-key migrations; trace CLI commands and compare outputs under /app/logs/ against the contracts in docs/output-contracts.md.
