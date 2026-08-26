# We run a small group of replicas that keep an ordered, authenticated log of clie

Submission: `b238a6ec-530b-4788-93d9-e02392edc2df`  
Slug: `we-run-a-small-group-of-replicas-that-keep-an-ordered-authen`  
Latest archive: `b238a6ec-530b-4788-93d9-e02392edc2df_submission_2026-07-17T13_47_22.996Z.zip`  
Revisions: 1

## Task summary

We run a small group of replicas that keep an ordered, authenticated log of client operations. Every replica shares one cluster key, but the network is hostile: it drops, reorders, duplicates, and replays messages, opens and heals partitions, and injects messages no replica ever sent. You write the replica fresh in /app/src/LogReplica.java against the Replica interface, MsgKind tags, and AuthCode helper. /app/docs/interface.md is the type, lifecycle, and timing reference, /app/docs/contract.md states the guarantees the group keeps, and bash /app/smoke.sh replays sample schedules. Run Viewstamped Replication over the six MsgKind tags. One replica is the primary for a view; it numbers each operation, prepares it to the others, and commits it once a majority store it. When replicas stop hearing the primary they change view, collecting a majority of view-change messages that carry each replica's log, and the new primary adopts the most current one. Authenticate every message under the cluster key and act on it only in the exchange it belongs to.

Required artifacts include: `/app/src/LogReplica.java`, `/app/docs/interface.md`, `/app/docs/contract.md`, `/app/smoke.sh`.

Author anonymous tagged this **hard** security task (message-authentication, replay-resistance, view-change-integrity, committed-operation-durability, crash-recovery, partition-tolerance).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1200s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `b238a6ec-530b-4788-93d9-e02392edc2df_submission_2026-07-17T13_47_22.996Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
