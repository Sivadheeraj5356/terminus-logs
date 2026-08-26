# Your working directory is /app, which contains cache_policy.md and tier.conf. Yo

Submission: `dbf97970-aede-47d5-8b42-417a1682f883`  
Slug: `your-working-directory-is-app-which-contains-cache-policy-md`  
Latest archive: `dbf97970-aede-47d5-8b42-417a1682f883_submission_2026-07-20T03_29_25.450Z (1).zip`  
Revisions: 6

## Task summary

Your working directory is /app, which contains cache_policy.md and tier.conf. You are provisioning read delegation for the eight build-artifact caches under /srv/ci-cache, using the real account tools (chown, chgrp, chmod, setfacl). The full model is in /app/cache_policy.md and the budgets and settle delay are in /app/tier.conf. The caches ship bare and owned by root. Do not write a program and do not add or remove any member of any group. The grader reads the state back with getent, stat and getfacl, and by switching to each runner and job account to attempt the real reads and writes the delegation allows or forbids. Each cache has one writer runner, a set of downstream jobs that must read it, and a set that must never read it (policy section 3). Read is delegated only through the four runner-group tiers, whose rosters are seeded and fixed (section 2). A cache may ride a tier only when that roster covers all of its required jobs and holds none of its forbidden jobs; the escalation column lists exactly those legal tiers in order. A cache does not just take the first tier it names. Each tier carries a demand budget, and a cache's weight does not count against its tier the instant it lands there. The charge lands settle_delay placements later, so a cache delegated while an earlier charge is still pending reads its tier as emptier than it settles and takes room it will not keep. Once every charge lands, an over-budget tier turns away its latest-placed occupant, which re-settles to the next legal tier in its escalation order and carries its own deferred charge, until every...

Required artifacts include: `/app/cache_policy.md`, `/app/tier.conf`.

Author anonymous tagged this **hard** system-administration task (linux, unix-groups, posix-acl, access-control, permissions).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 1200.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `dbf97970-aede-47d5-8b42-417a1682f883_submission_2026-07-20T03_29_25.450Z (1).zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
