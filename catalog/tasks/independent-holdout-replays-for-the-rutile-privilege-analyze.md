# Independent holdout replays for the rutile privilege analyzer disagree with the 

Submission: `023c4ea9-6a0a-477c-875e-b51ae5aa1621`  
Slug: `independent-holdout-replays-for-the-rutile-privilege-analyze`  
Latest archive: `023c4ea9-6a0a-477c-875e-b51ae5aa1621_submission_2026-07-17T06_38_40.613Z.zip`  
Revisions: 1

## Task summary

Independent holdout replays for the rutile privilege analyzer disagree with the platform analysis contract: exported edge inventories, escalation chains, and report attestations do not reconcile across the bundled holdout profile set. Restore full contract compliance for every holdout profile. Regenerated reports written to `/app/output/escalation_report.json` must include `profile`, `identity_count`, `edges`, `chains`, and `report_digest_hex` and satisfy the platform output schema, channel semantics, ordering invariants, and digest attestation rules. Contract-conformant exports depend on a corrected analyzer implementation; static or hand-authored artifacts alone are insufficient.

Required artifacts include: `/app/output/escalation_report.json`.

Author anonymous tagged this **medium** security task (go, security, iam, rbac, privilege-escalation, cloud-identity).

Time estimates: expert ~75 min, junior ~180 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `023c4ea9-6a0a-477c-875e-b51ae5aa1621_submission_2026-07-17T06_38_40.613Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
