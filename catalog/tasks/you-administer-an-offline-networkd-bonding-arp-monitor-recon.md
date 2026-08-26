# You administer an offline networkd bonding ARP-monitor reconcile deployment unde

Submission: `2f3ef62d-32d5-4dad-ae68-2a9c4c4c8c1a`  
Slug: `you-administer-an-offline-networkd-bonding-arp-monitor-recon`  
Latest archive: `2f3ef62d-32d5-4dad-ae68-2a9c4c4c8c1a_submission_2026-07-20T10_13_38.610Z.zip`  
Revisions in Dropbox: 6

## Task summary

You administer an offline networkd bonding ARP-monitor reconcile deployment under `/app/environment`. After a MAC failover drill the deployment no longer meets its documented operational policy: egress still steers toward a downed member, ARP monitor pressure never fully settles, a staging-only ghost peer keeps entering the working set, back-to-back drills stop lining up with the durable lineage ledger, and the local status probe reports convergence that the sealed artifacts do not support. The first drill after the incident often looks fine; it is the second and later drills, replays, and recover runs that drift. Build and run commands are in `/app/environment/docs/run_cmds.txt`. That build produces `/app/environment/build/vx_bond` (also `/app/bin/vx_run`, which must remain present and executable) and `/app/environment/build/bond_probe`. Member ids are in `/app/environment/docs/member_ids.txt`. Observable policy — membership (no required report row order), decay-once, digest/seed mismatch rejection, session-journal epochs, the durable lineage ledger and settle chain, seal replace, probe predicate, matrix digest (sorted by `lane_id`), q2m refresh durability, and digests — lives in `/app/environment/docs/formal_rules.md`.

Required artifacts include: `/app/environment`, `/app/environment/docs/run_cmds.txt`, `/app/environment/build/vx_bond`, `/app/bin/vx_run`, `/app/environment/build/bond_probe`, `/app/environment/docs/member_ids.txt`, `/app/environment/docs/formal_rules.md`, `/app/environment/data/rank_tbl.toml`.

Author anonymous tagged this **medium** system-administration task (bond, arp, networkd, failover, ghost-peer).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `2f3ef62d-32d5-4dad-ae68-2a9c4c4c8c1a_submission_2026-07-20T10_13_38.610Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
