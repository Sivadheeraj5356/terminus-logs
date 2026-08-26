# You are auditing breakglass emergency-access evidence for security-control viola

Submission: `c188016a-8869-47b5-a7d2-a873e10a26c6`  
Slug: `you-are-auditing-breakglass-emergency-access-evidence-for-se`  
Latest archive: `c188016a-8869-47b5-a7d2-a873e10a26c6_submission_2026-07-15T13_43_26.436Z (1).zip`  
Revisions in Dropbox: 6

## Task summary

You are auditing breakglass emergency-access evidence for security-control violations. The records in `/app/input_data` cover principals, protected resources, incident tickets, approvers, privileged access requests, approval decisions, session events, and revocations from a production emergency-access system. Produce the offline security ledger package at `/app/output_data/breakglass_ledger.json`, creating `/app/output_data` if needed. The output JSON has only `ledger_entries` and `severity_index`. Each ledger entry has only `entry_id`, `control`, `severity`, `principal`, `resource`, `first_evidence`, `evidence`, and `reason_codes`; `severity_index` has exactly `critical`, `high`, `medium`, and `low`. `/app/SPEC.md` is authoritative for the evidence schemas, approval-signature checks, event-chain integrity checks, requester eligibility controls, approval-count controls, ticket binding controls, ticket-scoped network and command controls, duration controls, network boundary controls, privileged command/session controls, aggregate approval concentration controls, evidence formats, reason codes, severity, deduplication, and sorting. Do not hard-code the bundled incident data.

Required artifacts include: `/app/input_data`, `/app/output_data/breakglass_ledger.json`, `/app/output_data`, `/app/SPEC.md`, `/app/src/main.rs`, `/app/input_data/*.tsv`.

Author anonymous tagged this **hard** security task (rust, security, breakglass, access-control, ledger).

Time estimates: expert ~120.0 min, junior ~900.0 min.

Harbor timeouts: agent 1200.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `c188016a-8869-47b5-a7d2-a873e10a26c6_submission_2026-07-15T13_43_26.436Z (1).zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
