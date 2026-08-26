End-to-end execution reports have been diverging from generated plans. Historical reporting and plan generation are already stable for this milestone. Three issues need attention in the execution simulation path that persists results to /app/db/history.db and writes /app/logs/execution_report.json.

Re-running the same session must not inflate passed_count or failed_count on identical runs. Interrupted rows in execution_results are historical records that must remain in the database across reruns even when they stay out of aggregated totals.

Failure detail objects in the execution report are missing the browser field. Each failure entry must identify which browser produced the failure.

Failure simulation must be scoped to the browser project being executed. For each spec under a plan project, derive pass or fail from filtered historical test_runs for that spec and browser pair using the same session-validity rules as historical reporting. A spec that fails under one browser must still simulate passed under another browser when that browser's filtered history does not support a failure.

Repair execution reporting so node cli.js run --session plan-sess-alpha produces stable counts on rerun, browser on failures, interrupted rows excluded from totals, and flaky_count reflecting specs with both passes and failures across browsers in the session. Execution report field layout is in /app/docs/output-contracts.md under the execution section.
