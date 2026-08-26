# The Colverton retention plane is the log-storage tier of a fleet observability s

Submission: `a5b2ad94-6ad1-4bf0-94bd-a27b6b664d1b`  
Slug: `the-colverton-retention-plane-is-the-log-storage-tier-of-a-f`  
Latest archive: `a5b2ad94-6ad1-4bf0-94bd-a27b6b664d1b_submission_2026-07-21T04_10_01.693Z.zip`  
Revisions in Dropbox: 1

## Task summary

The Colverton retention plane is the log-storage tier of a fleet observability stack: ingest collectors fanned out into log indices, each index a bank of per-service channels that service streams write their volume into, administered cycle by cycle by the retention warden `spoolward`. The warden works each cycle's change orders against the plane register, the source inventory, the operator roster and the standing streams (streams routed onto channels and detached back off, indices force-flushed, retention holds placed and lifted on either a source or its channel, streams pinned against purging, indices quiesced for maintenance and resumed, collectors decommissioned out of service, index budgets retuned), closes every cycle by expiring the retention holds due and purging every index whose volume has climbed past its budget, and records how the plane stands as one report. As the plane runs today the warden keeps the charter only in part, and the report it records does not match the plane on the floor. Your duty is to administer the warden into full conformance with the charter, so that, run over the plane as it stands, it records exactly the report the charter calls for, byte for byte on every run. The binding charter is `/app/charter/RETENTION-CHARTER.txt`, a numbered list of clauses L1 onward; the clauses are the whole charter and nothing outside them binds. They fix the plane root and its files, the two operator roles with their index grants and collector charges, the screening of change orders and the seq gate, the one-stream-per-source and one-stream-per-channel...

Required artifacts include: `/app/charter/RETENTION-CHARTER.txt`, `/app/plane`, `/app/output/spoolward_report.json`.

Author anonymous tagged this **hard** system-administration task (log-retention, observability, storage-capacity, retention-policy).

Time estimates: expert ~240.0 min, junior ~480.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `a5b2ad94-6ad1-4bf0-94bd-a27b6b664d1b_submission_2026-07-21T04_10_01.693Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
