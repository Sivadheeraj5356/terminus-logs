# CLI output contracts

This document defines the JSON shapes written under /app/logs/ by the flaky-repro CLI.

## report.json

Written by node cli.js report to /app/logs/report.json.

The report summarizes historical flaky prioritization. It includes a top_flaky array sorted by fail_count descending, with spec_file ascending as the secondary sort key when fail_count ties; each element carries spec_file, browser, fail_count, and total_runs. The by_browser object is keyed by browser name (chromium, firefox, webkit) and maps each browser to an array of flaky entries containing spec_file, fail_count, and total_runs without a nested browser field because entries are already grouped. The total_flaky_combos field counts spec+browser pairs that showed both failures and passes in valid history.

## plan.json

Written by node cli.js plan to /app/logs/plan.json.

The plan carries session_id matching the --session argument, total_specs counting each flaky spec+browser pair included in the plan rather than the number of unique spec file paths alone, and a projects array with one entry per browser. Each project entry includes name from the database, browser, retries and workers and shards from configuration, and testMatch listing spec paths assigned to that browser.

## execution_report.json

Written by node cli.js run to /app/logs/execution_report.json.

The report carries session_id, passed_count and failed_count for non-interrupted simulated results, flaky_count for specs that had both passes and failures across browser runs in this session, and a failures array. Each failure entry includes spec_file, browser (chromium, firefox, or webkit), retry_count, and status.
