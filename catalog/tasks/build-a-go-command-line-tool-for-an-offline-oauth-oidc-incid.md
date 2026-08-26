# Build a Go command line tool for an offline OAuth/OIDC incident review. It needs

Submission: `441f5efc-b7ab-4668-b49c-9bf0d34b26c6`  
Slug: `build-a-go-command-line-tool-for-an-offline-oauth-oidc-incid`  
Latest archive: `441f5efc-b7ab-4668-b49c-9bf0d34b26c6_submission_2026-07-09T16_10_05.511Z.zip`  
Revisions: 2

## Task summary

Build a Go command line tool for an offline OAuth/OIDC incident review. It needs to replay a token-exchange ledger, report the active exposure at the review timestamp, and choose the canonical bounded remediation plan. Keep source at `/app/task_file/src/token_audit.go` and build `/app/task_file/bin/token_audit`. Run it exactly as `--input <case-file> --output <report-file>` in that order, with no extra arguments. Missing, reordered, repeated, or extra arguments are errors: exit nonzero and do not create the output file. Invalid case-file syntax is also an error: exit nonzero and do not create or modify the output file. The public case is `/app/task_file/input/public_exchange.txt`; hidden cases use the same visible format and may use versions `1` through `3`. Do not edit `/app/task_file/input/`, including the public fixture; its exact contents are part of the task contract.

Required artifacts include: `/app/task_file/src/token_audit.go`, `/app/task_file/bin/token_audit`, `/app/task_file/input/public_exchange.txt`, `/app/task_file/input/`, `/app/task_file/oidc_exchange_audit_spec.txt`.

Author Anonymous tagged this **hard** security task (oauth, oidc, token-exchange, event-log-replay, access-control, security-audit, lineage-analysis, combinatorial-planning).

Time estimates: expert ~420.0 min, junior ~2100.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `441f5efc-b7ab-4668-b49c-9bf0d34b26c6_submission_2026-07-09T16_10_05.511Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
