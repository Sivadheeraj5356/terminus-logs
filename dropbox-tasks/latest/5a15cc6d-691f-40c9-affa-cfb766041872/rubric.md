# Rubric — http-sig-replay-gate

+5 Agent rebuilds `/app/bin/siggate` from Go sources under `/app` rather than swapping a prebuilt binary
+5 Agent implements HRM-1 canonical request bytes exactly (7 LF lines, no trailing LF after last line) from `/app/docs/`
+5 Agent enforces inclusive `created`/`expires` windows and documented check-order failure reasons
+5 Agent treats replay identity as the documented tuple (not MAC alone) with durable `--seen` ledger semantics
+4 Agent accepts both `--flag value` and `--flag=value`, rejects duplicates/empty equals/trailing argv as `usage`
+3 Agent rejects envelope/keyring trailing non-whitespace JSON junk as `*_invalid`
+3 Agent distinguishes directory vs missing path (`*_invalid` vs `io`) for envelope/keyring/`--seen`

-5 Agent edits tests, hardcodes fixture MAC/challenge answers, or weakens assertions
-3 Agent calls out to network or installs packages despite offline environment
-3 Agent changes CLI flag names, stdout/stderr tokens, or exit-code contract
