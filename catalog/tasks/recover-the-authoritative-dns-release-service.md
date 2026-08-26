# # Recover the authoritative DNS release service

Submission: `baebd414-2e04-43ac-9fa9-71f70cc9403e`  
Slug: `recover-the-authoritative-dns-release-service`  
Latest archive: `baebd414-2e04-43ac-9fa9-71f70cc9403e_submission_2026-07-18T04_47_53.736Z.zip`  
Revisions: 4

## Task summary

The failed change window left the Harbor authoritative DNS service without a releasable configuration. Recover it from the incident evidence in `/app/evidence` and leave a production-shaped BIND configuration that operators can validate and start. This is a system-administration task: do not build a parser, reconciler, or other custom program. Do not modify anything under `/app/evidence`. Install all recovered files under `/app/live` and write the custody manifest described below under `/app/recovery`. The service must validate with `named-checkconf /app/live/named.conf`, and this command must start it in the foreground: `named -c /app/live/named.conf -g -u root`. Recovery couples destination-address views, authoritative forward and reverse data, delegation glue, RPZ exception precedence, TSIG transfer boundaries, narrowly scoped RFC 2136 updates, journal survival across a full daemon restart, mutable-zone placement, and evidence custody. Several configurations validate syntactically yet leak a view, authorize an apex or sibling update, lose accepted state 

Required artifacts include: `/app/evidence`, `/app/live`, `/app/recovery`, `/app/live/named.conf`, `/app/live/run`, `/app/live/zones`, `/app/evidence/recovery-policy.txt`, `/app/live/zones/internal.rpz`.

Author Anonymous tagged this **hard** system-administration task (dns, bind9, incident-recovery, split-horizon, tsig, rpz).

Time estimates: expert ~150.0 min, junior ~720.0 min.

Harbor timeouts: agent 1800.0s, verifier 240.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `baebd414-2e04-43ac-9fa9-71f70cc9403e_submission_2026-07-18T04_47_53.736Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
