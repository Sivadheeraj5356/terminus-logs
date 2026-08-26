# Build-artifact cache delegation policy

This host runs eight CI pipelines. Each pipeline's build runner writes a stream of artifact files into
its own cache under /srv/ci-cache, and a fixed set of downstream job accounts is allowed to read that
cache while a fixed set is forbidden from ever pulling from it. Reads are delegated only through the four
shared runner-group tiers. Your job is to bring every cache and every future artifact file to the
delegated state this policy fixes, using the real account tools. Do not write a program and do not add or
remove any member of any group.

## 1. Accounts

Downstream jobs (the readers): job1 job2 job3 job4 job5 job6. Each keeps its own private primary group of
the same name and its tier memberships are already seeded and must not change.

Runners (the writers): runA runB runC runD. Each keeps its own private primary group of the same name.
Every runner owns two caches as shown in the pipeline table.

## 2. Runner-group tiers and their seeded rosters

Read is delegated only through these four tiers. Their rosters are fixed and already seeded; you do not
edit them. A cache delegated through a tier grants read to exactly this roster.

    rgW   job1 job3 job6
    rgX   job2 job3 job6
    rgY   job1 job4 job6
    rgZ   job2 job5 job6

## 3. Pipelines

Each row is a cache directory under /srv/ci-cache. writer is the runner that owns the cache. required
lists the jobs that must pull the artifacts; forbidden lists the jobs that must never see them. A tier is
legal for a cache only when its roster contains every required job and none of the forbidden jobs,
because a roster grants read on every cache it is named on, so a forbidden job in the roster would leak.
escalation is the fixed order in which the cache tries its legal tiers. weight is the demand weight the
cache places on whichever tier it lands in. placement_order is the order in which the caches are settled.

    cache   writer  required  forbidden       escalation      weight  placement_order
    lint    runA    job3      job5            rgW rgX         3       1
    api     runB    job6      job2            rgW rgY         3       2
    web     runA    job6      job5            rgW rgX rgY     1       3
    infra   runB    job2      job4            rgX rgZ         3       4
    data    runC    job3      job4 job5       rgW rgX         2       5
    mobile  runC    job6      job1            rgX rgZ         1       6
    ml      runD    job6      job1 job4       rgX rgZ         1       7
    docs    runD    job6      job4            rgW rgX rgZ     1       8

## 4. How each cache settles

A cache does not simply take the first tier in its escalation order. Every tier carries a demand budget
(rgW_budget, rgX_budget, rgY_budget in /app/tier.conf; rgZ is the unbounded tail), and a cache's weight
does not count against its tier the instant it lands there. The charge lands settle_delay placements
later, so a cache delegated while an earlier placement's charge is still pending reads its tier as
emptier than it settles and takes room it will not keep. Once every charge has landed a tier can sit over
budget, and it is brought back within budget by turning away its latest-placed occupant, which re-settles
to the next legal tier in its escalation order and carries its own deferred charge in turn, until every
bounded tier is within its budget. Work the settling out for the eight caches under the live budgets and
settle_delay, and delegate each cache through the tier it comes to rest in, not the first tier its
escalation order names. A solver that charges each placement the instant its cache lands, skipping the
deferred window, misplaces several caches and fails. Read every budget and the settle delay live from
/app/tier.conf.

## 5. The delegated state per cache

For each cache directory, once you know its settled tier:

Ownership and mode. The directory is owned by root and group-owned by the writer runner's private group,
mode 2770. The setgid bit stamps the writer's group onto every artifact file dropped later. The other
bits stay closed so no unrelated account may enter.

Traverse for the tier. Put a named access ACL g:<tier>:r-x on the directory itself so the settled roster
can enter and list the cache. Without it the roster cannot reach the files even though the files name the
tier.

Inheritance for later drops. New artifact files must come out writable by the writer runner and readable
but not writable by the settled tier roster, and this must hold under any umask the runner uses,
including a restrictive 0077. Set default entries so that the writer runner's group and the writer runner
user both inherit rwx, the settled tier inherits r-x, and the default mask is rwx. A plain new file whose
create mode has no execute folds its own mask down to rw, so the tier roster comes out read only with no
write and no execute; the writer keeps write. Do not group-own the directory by the tier and do not give
the tier a group-write default, either of which leaks write onto every new artifact file. Do not clamp
the default mask below rwx, which would strip the writer's own write off new files.

## 6. What the grader reads back

The grader reads tier rosters with getent, reads ownership and mode with stat, reads every ACL with
getfacl, and switches to each job and runner with runuser to attempt the real reads and writes. It
re-solves the settled tier of every cache from the same inputs it can read, the seeded rosters, each
cache's required and forbidden jobs and weight, and the budgets and settle_delay, and it re-solves a
second time with settle_delay forced to zero to confirm the deferred window is load bearing. For every
cache the writer runner must read and write, every settled roster job must read but not write, and every
forbidden and unrelated job must be denied read and write. The grader also drops a fresh artifact file
into each cache as the writer under umask 0022 and again under umask 0077 and confirms the settled roster
reads it while it stays read only to them.
