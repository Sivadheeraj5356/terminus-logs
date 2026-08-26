# Journal vacuum oneshot ledger skew

Submission: `1036fcde-d250-446c-8149-ec417238e19e`  
Slug: `journal-vacuum-oneshot-ledger-skew`  
Latest archive: `1036fcde-d250-446c-8149-ec417238e19e_submission_2026-07-17T11_58_17.225Z.zip`  
Revisions in Dropbox: 1

## Task summary

Journal vacuum oneshot ledger skew After journal vacuum maintenance on this host, the shard-export oneshot unit (`verify-journal-export.service`) loses byte-ledger parity between `StandardOutput=journal` and `StandardOutput=file` launch settings. `journalctl -u verify-journal-export` shows truncated progress lines and collector-socket write abort when journald recycles mid-burst; the file-backed unit profile completes quietly on the same fixture packs.

Required artifacts include: `/app/environment`, `/app/environment/docs/journal_contract.md`, `/app/output`, `/app/bin/verify-journal-runs`, `/app/output/run_records.json`, `/app/output/export_trace.jsonl`, `/app/output/span_journal.jsonl`, `/app/output/completion_manifest.jsonl`.

Author anonymous tagged this **hard** system-administration task (systemd, journald, journal-vacuum, host-policy, wal-ledger, oneshot).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `1036fcde-d250-446c-8149-ec417238e19e_submission_2026-07-17T11_58_17.225Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
