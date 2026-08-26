Your working directory is /app, which contains cache_policy.md and tier.conf. You are provisioning read
delegation for the eight build-artifact caches under /srv/ci-cache, using the real account tools (chown,
chgrp, chmod, setfacl). The full model is in /app/cache_policy.md and the budgets and settle delay are in
/app/tier.conf. The caches ship bare and owned by root. Do not write a program and do not add or remove
any member of any group. The grader reads the state back with getent, stat and getfacl, and by switching
to each runner and job account to attempt the real reads and writes the delegation allows or forbids.

Each cache has one writer runner, a set of downstream jobs that must read it, and a set that must never
read it (policy section 3). Read is delegated only through the four runner-group tiers, whose rosters are
seeded and fixed (section 2). A cache may ride a tier only when that roster covers all of its required
jobs and holds none of its forbidden jobs; the escalation column lists exactly those legal tiers in
order. A cache does not just take the first tier it names. Each tier carries a demand budget, and a
cache's weight does not count against its tier the instant it lands there. The charge lands settle_delay
placements later, so a cache delegated while an earlier charge is still pending reads its tier as emptier
than it settles and takes room it will not keep. Once every charge lands, an over-budget tier turns away
its latest-placed occupant, which re-settles to the next legal tier in its escalation order and carries
its own deferred charge, until every bounded tier is within budget. Work the settling out for all eight
caches under the live budgets and settle_delay and delegate each cache through the tier it comes to rest
in. A solver that charges each placement the instant its cache lands misplaces several caches and fails.

Own each cache by root with the writer runner's private group at mode 2770, name the settled tier on the
directory so its roster can traverse, and set default entries so every new artifact file inherits writer
write and tier-roster read only, holding even under umask 0077. Section 5 gives the exact ownership,
mode, access ACL and default ACL each cache must carry. Do not group-own a cache by its tier and do not
give the tier a default group write, either of which leaks write onto new artifacts.
