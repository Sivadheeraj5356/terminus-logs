# The security operations team needs an offline adjudicator for signed emergency b

Submission: `357dea52-1def-4f5d-a0b9-228e60de1124`  
Slug: `the-security-operations-team-needs-an-offline-adjudicator-fo`  
Latest archive: `357dea52-1def-4f5d-a0b9-228e60de1124_submission_2026-07-20T17_33_40.894Z.zip`  
Revisions in Dropbox: 1

## Task summary

The security operations team needs an offline adjudicator for signed emergency break-glass access events. It must verify authorization-event signatures, reconstruct privileged session state, apply gateway lock state, quorum, separation-of-duty, control-window, token-replay, and risk rules, then write the exact access-control adjudication report. Implement the Go access-control adjudicator at `/workspace/cmd/breakglass-ledger/main.go` and build the executable at `/workspace/bin/breakglass-ledger`. The runtime is offline. It must run as:

Required artifacts include: `/output/breakglass_ledger_report.json`.

Author Anonymous tagged this **hard** security task (security, access-control, incident-response, breakglass, authorization, hmac, go).

Time estimates: expert ~180 min, junior ~1200 min.

Harbor timeouts: agent 1500s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `357dea52-1def-4f5d-a0b9-228e60de1124_submission_2026-07-20T17_33_40.894Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
