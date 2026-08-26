# # Routing ownership under in-place profile reload

Submission: `541ca227-bc27-4924-bd15-107eb21e61a9`  
Slug: `routing-ownership-under-in-place-profile-reload`  
Latest archive: `541ca227-bc27-4924-bd15-107eb21e61a9_submission_2026-07-18T18_49_38.317Z.zip`  
Revisions: 1

## Task summary

`/app/bin/linkctl` is the offline link-policy control plane for topology profiles under `/app/data/topology_w3/` and grant/withdraw events in `/app/var/grant_feed.jsonl`. Operators drive cold boot, in-place profile reload, and WAL-backed state reconstruction with `bash /app/scripts/run_link_ops.sh <profile>` and `linkctl recover --root /app/var/state --out /app/output`. Each run must leave `/app/output/effective_fib.json`, `/app/output/link_status.json`, and `/app/output/reconfigure_journal.jsonl` aligned with `/app/environment/docs/operator_contract.md`:

Required artifacts include: `/app/bin/linkctl`, `/app/data/topology_w3/`, `/app/var/grant_feed.jsonl`, `/app/scripts/run_link_ops.sh`, `/app/var/state`, `/app/output`, `/app/output/effective_fib.json`, `/app/output/link_status.json`.

Author anonymous tagged this **hard** system-administration task (routing-policy, fib, network-admin, reload, wal).

Time estimates: expert ~240 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `541ca227-bc27-4924-bd15-107eb21e61a9_submission_2026-07-18T18_49_38.317Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
