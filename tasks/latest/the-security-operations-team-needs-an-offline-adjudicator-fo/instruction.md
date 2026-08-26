The security operations team needs an offline adjudicator for signed emergency break-glass access events. It must verify authorization-event signatures, reconstruct privileged session state, apply gateway lock state, quorum, separation-of-duty, control-window, token-replay, and risk rules, then write the exact access-control adjudication report.

Implement the Go access-control adjudicator at `/workspace/cmd/breakglass-ledger/main.go` and build the executable at `/workspace/bin/breakglass-ledger`. The runtime is offline. It must run as:

`/workspace/bin/breakglass-ledger /workspace/task_file/breakglass_ledger_case.json /workspace/output/breakglass_ledger_report.json`

The first argument is the input JSON path and the second argument is the output JSON path. Create the output directory if needed, overwrite the output file, and keep the adjudication logic inside the Go binary; do not shell out to Python, shell scripts, or another helper.

The input case is `/workspace/task_file/breakglass_ledger_case.json`. The full input schema, signature transcript, authorization-event retention rules, privileged-session state transitions, denial reasons, ordering rules, and required output JSON are defined in `/workspace/task_file/docs/SPEC.md`; those rules are part of the exact-match grading contract. Exact-match grading is used after JSON parsing, so array order, field names, strings, booleans, integers, and empty-array behavior matter exactly.
