# This is a security finding, not a routine bug report: chainaudit's tamper-eviden

Submission: `d06b4e3f-699c-45e7-953c-87a677cff59b`  
Slug: `this-is-a-security-finding-not-a-routine-bug-report-chainaud`  
Latest archive: `d06b4e3f-699c-45e7-953c-87a677cff59b_submission_2026-07-16T23_19_20.855Z.zip`  
Revisions: 2

## Task summary

This is a security finding, not a routine bug report: chainaudit's tamper-evidence guarantee for the compliance event log has a detection bypass. Since last month's storage migration, verify can't reliably tell real tampering from harmless encoding differences — a checkpoint genuinely altered during the incident currently verifies as clean, while unrelated streams get flagged as corrupt, exactly the noise that trains people to ignore alerts that matter. Until this is closed, the tamper-evidence property this system exists to provide does not actually hold. Two things, in order. First, prove the bypass is real: copy /app/data/chainaudit.db to /app/out/exploit.db, tamper with one event the way an attacker with database write access but no signing key actually could, and record what you changed in /app/out/exploit_report.json as {"stream_id": ..., "seq": ...}. Construct new tampering yourself against a stream that isn't already flagged, and patch the row's own stored hash to match your edit — a check that only catches unpatched tampering isn't proving much.

Required artifacts include: `/app/data/chainaudit.db`, `/app/out/exploit.db`, `/app/out/exploit_report.json`, `/app/CHAINAUDIT-SPEC.md`, `/app/out/verify_report.json`, `/app/out/compact_manifest.json`, `/app/data/NOW.txt`.

Author anonymous tagged this **hard** security task (sqlite, merkle-tree, hmac-sha256, cryptographic-verification, kms-mock, tamper-detection).

Time estimates: expert ~120 min, junior ~420 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `d06b4e3f-699c-45e7-953c-87a677cff59b_submission_2026-07-16T23_19_20.855Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
